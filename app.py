from flask import Flask, render_template, request, session, redirect, url_for, send_file, send_from_directory
import os
import sys
import uuid
import hashlib
import random
import pymysql.cursors
from functools import wraps
from werkzeug.utils import secure_filename
from datetime import datetime
import time

app = Flask(__name__)
app.secret_key = '''5d1f4aa2ca12aefa18e25628ba680e81f2fb1f
                    7dde78c174396228cc3170285e8a459037bb21
                    a375b939d6e82d5f0aba2bdec389c610fae299
                    428f3197ca3921c2c00c59fa1ceb1417cc142a
                    d763826be48983e4a96aed96436c621b9809e2
                    d58b309a94ab9dfd1769647ec6fd5d90821c40
                    Yes, the spaces are part of the key'''
IMAGES_DIR = os.path.join(os.getcwd(), "images")
conn =   pymysql.connect(host       = sys.argv[1],
                           port     = int(sys.argv[2]),
                           user     = sys.argv[3],
                           password = sys.argv[4],
                           db       = sys.argv[5],
                           charset  = sys.argv[6],
                           cursorclass=pymysql.cursors.DictCursor)
                           
####################
##  LOGIN STUFFS  ##
####################

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")


@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with conn.cursor() as cursor:
            query = "SELECT * FROM Person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with conn.cursor() as cursor:
                query = "INSERT INTO Person (username, password, firstName, lastName) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
                conn.commit()
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
@login_required
def logout():
    session.pop("username")
    return redirect("/")


####################
##  IMAGE STUFFS  ##
####################
@app.route("/postphoto", methods=["GET"])
@login_required
def upload():
    return render_template("postphoto.html")

dir_path = os.path.dirname(os.path.realpath(__file__))
imagesFolder = os.path.join(dir_path, "images", "")
def allowed_image(filename):
    # We only want files with a . in the filename
    if not "." in filename:
        return False
    # Split the extension from the filename
    ext = filename.rsplit(".", 1)[1]
    # Check if the extension is in ALLOWED_IMAGE_EXTENSIONS
    if ext.upper() in ["JPEG", "JPG", "PNG", "GIF", "BMP"]:
        return True
    else:
        return False
@app.route('/postsubmit', methods=['POST'])
@login_required
def submitphoto():
    if request.method != "POST":
        return redirect('/postphoto')
    if request.files:
        image = request.files["image"]
        if image.filename == "":
            return redirect("/postphoto",error="File Had No Name")
        if not allowed_image(image.filename):
            return redirect("/postphoto",error="Invalid Filetype")
        filename = secure_filename(image.filename)
        filename = str(random.randint(-90210,90210))+filename
        filepath = os.path.join(imagesFolder, session['username']+"."+filename)
        #cursor used to send queries
        all=0
        if "all" in request.form:
            all=1
        #executes query
        
        query = "INSERT INTO Photo ( postingdate, filepath, allFollowers, caption, photoPoster) VALUES( %s, %s, %s, %s, %s)"
        with conn.cursor() as cursor:
            cursor.execute(query, (datetime.now(),
                            filepath,
                            all,
                            request.form["caption"],
                            session['username']))
            conn.commit()
            if all == 0:
                query='Select photoID from Photo where photoPoster=%s AND filepath=%s'
                cursor.execute(query, (session['username'], filepath) )
                all = cursor.fetchone()
                all = all['photoID']
        image.save(filepath)
        if "all" not in request.form:
            return redirect("/pickgroups/"+str(all))
        return redirect('/home')
    return render_template('postphoto.html')

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo"
    with conn.cursor() as cursor:
        cursor.execute(query)
    data = cursor.fetchall()
    return render_template("images.html", images=data)


def has_permission(photoID, user):
    return 1

@app.route('/image/<photoID>')
@login_required
def imagegetter(photoID):
    if has_permission(photoID, session['username']):
        with conn.cursor() as cursor:
            query = "SELECT filepath FROM Photo WHERE photoID = %s "
            cursor.execute(query, (photoID))
            data = cursor.fetchone()
            head_tail = os.path.split(data['filepath'])
        return send_from_directory(head_tail[0], head_tail[1])
    else:
        return send_from_directory(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static'), "ERROR.png")

@app.route('/removephoto', methods=['GET','POST'])
@login_required
def removephototo():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    if "pid" not in request.form:
        return "No", 418
    data = None
    with conn.cursor() as cursor:
        photoID = request.form['pid']
        query = "SELECT * FROM Photo WHERE photoPoster = %s AND photoID = %s "
        cursor.execute(query, (session['username'], photoID))
        data = cursor.fetchone()
    if not data:
        return "No", 418
    with conn.cursor() as cursor:
        query = "DELETE FROM SharedWith WHERE groupOwner = %s AND photoID = %s"
        cursor.execute(query, (session['username'], photoID))
        query = "DELETE FROM Photo WHERE photoPoster = %s AND photoID = %s"
        cursor.execute(query, (session['username'], photoID))
        conn.commit()
    return redirect( '/profile' )

@app.route('/imginfo/<photoID>')
@login_required
def imginf(photoID):
    if not has_permission(photoID, session['username']):
        return "No", 418
    with conn.cursor() as cursor:
        query = "select * from Photo WHERE photoID = %s"
        cursor.execute(query, (photoID))
        item = cursor.fetchone()
        query = "select * from Tagged WHERE photoID = %s AND tagstatus = 1"
        cursor.execute(query, (photoID))
        tags = cursor.fetchall()
        query = "select * from Person WHERE username = %s"
        cursor.execute(query, (item['photoPoster']))
        person = cursor.fetchone()
    return render_template('imginfo.html', item=item, tags=tags, person=person)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/pickgroups/<photoID>')
@login_required
def pickgroups(photoID):
    data = None
    dataNot=[]
    dataYes=[]
    pid = photoID
    with conn.cursor() as cursor:
        query = "SELECT * FROM Photo WHERE photoPoster = %s AND photoID = %s "
        cursor.execute(query, (session['username'], pid))
        data = cursor.fetchone()
    if not data:
        redirect('/')
    with conn.cursor() as cursor:
        query = '''SELECT * FROM `Friendgroup` 
                    WHERE `groupOwner` = %s and
                    `groupName` not in
                    (
                        select groupName from SharedWith 
                            where groupOwner=%s and 
                            photoID = %s
                    )'''
        cursor.execute(query, (session['username'], session['username'], pid))
        dataNot = cursor.fetchall()
        query = '''SELECT * FROM `Friendgroup` 
                    WHERE `groupOwner` = %s and
                    `groupName` in
                    (
                        select groupName from SharedWith 
                            where groupOwner=%s and 
                            photoID = %s
                    )'''
        cursor.execute(query, (session['username'], session['username'], pid))
        dataYes = cursor.fetchall()
        
    return render_template('pickgroups.html', dataNot=dataNot, dataYes=dataYes, pid=pid )

#"/rmpphoto5group"
@app.route('/rmphoto5group', methods=['GET', 'POST'])
@login_required
def rm5group():
    if request.method != "POST" or 'pid' not in request.form or 'grp' not in request.form:
        return redirect('/')
    data = None
    with conn.cursor() as cursor:
        query ='''SELECT * FROM Friendgroup
                    WHERE groupOwner = %s AND
                        groupName = %s '''
        cursor.execute(query,(session['username'],request.form['grp']))
        data= cursor.fetchall()
    if not data: ##Make sure they own the group
        return redirect('/mygroups')
    with conn.cursor() as cursor:
        query = ''' SELECT * FROM `Photo` 
                    WHERE `photoPoster`=%s AND 
                        `photoID`= %s '''
        cursor.execute(query,(session['username'],request.form['pid']))
        data= cursor.fetchall()
    if not data: ##Make sure they own th photo
        return redirect('/mygroups')
    with conn.cursor() as cursor:
        query = '''
                DELETE FROM `SharedWith` WHERE 
                `groupOwner` = %s AND 
                `groupName` = %s AND `photoID` = %s
                '''
        cursor.execute(query, (session['username'], request.form['grp'], request.form['pid']))
        conn.commit()
    return redirect("/pickgroups/"+request.form['pid'])
#"/addphoto2group"
@app.route('/addphoto2group', methods=['GET', 'POST'])
@login_required
def add2group():
    if request.method != "POST" or 'pid' not in request.form or 'grp' not in request.form:
        return redirect('/')
    data = None
    with conn.cursor() as cursor:
        query ='''SELECT * FROM Friendgroup
                    WHERE groupOwner = %s AND
                        groupName = %s '''
        cursor.execute(query,(session['username'],request.form['grp']))
        data= cursor.fetchall()
    if not data: ##Make sure they own the group
        return redirect('/mygroups')
    with conn.cursor() as cursor:
        query = ''' SELECT * FROM `Photo` 
                    WHERE `photoPoster`=%s AND 
                        `photoID`= %s '''
        cursor.execute(query,(session['username'],request.form['pid']))
        data= cursor.fetchall()
    if not data: ##Make sure they own the photo
        return redirect('/mygroups')
    with conn.cursor() as cursor:
        query = '''
INSERT INTO `SharedWith`(`groupOwner`, `groupName`, `photoID`) VALUES (%s ,%s, %s)
                '''
        cursor.execute(query, (session['username'], request.form['grp'], request.form['pid']))
        conn.commit()
    return redirect("/pickgroups/"+request.form['pid'])
    

########################
##  Group Management  ##
########################
@app.route('/mygroups')
@login_required
def mygroups():
    if session.get("username") is None:
        return redirect('/')

    query = "SELECT groupName, description FROM Friendgroup WHERE groupOwner = %s"
    with conn.cursor() as cursor:
        cursor.execute(query,(session['username']))
        data = cursor.fetchall()

    return render_template('mygroups.html', data = data)

@app.route('/makegroup', methods=['GET', 'POST'])
@login_required
def makegroup():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')

    query = "INSERT INTO Friendgroup(groupOwner, groupName, description) VALUES (%s, %s, %s)"
    with conn.cursor() as cursor:
        cursor.execute(query, (session['username'], request.form['groupname'], request.form['desc']))
        conn.commit() 
    return redirect('/mygroups')

@app.route('/modifygroup/<groupN>', methods=['GET', 'POST'])
@login_required
def modifygroup(groupN):
    
    dataYes = []
    dataNot = []
    photos = []
    gtit=None
    with conn.cursor() as cursor:
        query = """SELECT * FROM Friendgroup
                   WHERE groupOwner = %s AND
                        groupName = %s"""
        cursor.execute(query,(session['username'], groupN))
        gtit = cursor.fetchone()
        
    if not gtit:
        return redirect('/mygroups')
    with conn.cursor() as cursor:
        gtit = gtit['description']
        query = """ SELECT * FROM Person WHERE username IN
                (SELECT member_username from BelongTo 
                WHERE owner_username = %s AND
                groupName = %s)"""
        cursor.execute(query,(session['username'], groupN))
        dataYes = cursor.fetchall()
        query = """ SELECT * FROM Person WHERE username IN
                (
                SELECT username_follower FROM Follow 
                    WHERE username_followed = %s AND
                        followstatus = 1 AND
                        username_follower NOT IN
                            (
                            SELECT member_username from BelongTo 
                            WHERE owner_username = %s AND
                            groupName = %s
                            )
                )"""
        cursor.execute(query,(session['username'],session['username'], groupN))
        dataNot = cursor.fetchall()
        query = """SELECT * FROM Photo
                   WHERE photoID IN
                   (
                        SELECT photoID FROM SharedWith
                        WHERE groupOwner = %s AND
                            groupName = %s
                   )"""
        cursor.execute(query,(session['username'], groupN))
        photos = cursor.fetchall()    
    return render_template('modifygroup.html', gtit = gtit, gname = groupN, dataYes=dataYes, dataNot=dataNot, photos=photos)

@app.route('/addtogroup', methods=['GET', 'POST'])
@login_required
def addtogroup():
    if request.method != "POST" or 'groop' not in request.form or 'fren' not in request.form:
        return redirect('/')
    with conn.cursor() as cursor:
        query ='''SELECT * FROM Friendgroup
                    WHERE groupOwner = %s AND
                        groupName = %s '''
        cursor.execute(query,(session['username'],request.form['groop']))
        data= cursor.fetchall()
    if not data: ##Make sure they own the group
        return redirect('/mygroups')
    data = None
    with conn.cursor() as cursor:
        query = ''' SELECT * FROM `Follow` 
                    WHERE `username_followed`=%s AND 
                        `username_follower`=%s AND
                        `followstatus`= 1'''
        cursor.execute(query,(session['username'],request.form['fren']))
        data= cursor.fetchall()
    if not data: ##Make sure they have the follower
        return redirect('/mygroups')
    with conn.cursor() as cursor:
        query = '''
                INSERT INTO `BelongTo`(`member_username`, `owner_username`, `groupName`) 
                VALUES (%s, %s, %s)
                '''
        cursor.execute(query, (request.form['fren'],session['username'], request.form['groop']))
        conn.commit()
    return redirect('/modifygroup/'+request.form['groop'])

@app.route('/rmfromgroup', methods=['GET', 'POST'])
@login_required
def rmfromgroup():
    if request.method != "POST" or 'groop' not in request.form or 'fren' not in request.form:
        return redirect('/')
    with conn.cursor() as cursor:
        query ='''SELECT * FROM Friendgroup
                    WHERE groupOwner = %s AND
                        groupName = %s '''
        cursor.execute(query,(session['username'],request.form['groop']))
        data= cursor.fetchall()
    if not data: ##Make sure they own the group
        return redirect('/mygroups')
    with conn.cursor() as cursor:
        query = '''SELECT * FROM `BelongTo` WHERE `member_username` = %s AND
                     `owner_username` = %s AND
                     `groupName` = %s'''
        cursor.execute(query,(request.form['fren'],session['username'],request.form['groop'] ))
        data= cursor.fetchall()
    if not data: ##Make sure person is in group
        return redirect('/mygroups')
    with conn.cursor() as cursor:
        query = '''
                DELETE FROM `BelongTo`WHERE `member_username` = %s AND
                `owner_username` = %s AND `groupName` = %s
                '''
        cursor.execute(query, (request.form['fren'],session['username'], request.form['groop']))
        conn.commit()
    return redirect('/modifygroup/'+request.form['groop'])


##############################
##  Find Friends And Follows##
##############################
@app.route('/searchfriends', methods=['GET', 'POST'])
@login_required
def searchfriends():
    
    if request.method != "POST" or "fren" not in request.form:
        return redirect('/')    
    query = """SELECT username FROM Person WHERE username <> %s 
                AND username LIKE %s AND 
                username NOT IN 
                (SELECT username_followed FROM Follow
                 WHERE username_follower =%s          )"""
    with conn.cursor() as cursor:
        cursor.execute(query, (session['username'] ,"%"+request.form['fren']+"%", session['username']))
        data = cursor.fetchall()

    return render_template('browsefriends.html', data=data)

@app.route('/addfollower', methods=['GET', 'POST'])
@login_required
def addfollower():
    
    if request.method != "POST" or "fren" not in request.form:
        return redirect('/')

    query = "INSERT INTO Follow(username_followed, username_follower, followstatus) VALUES (%s, %s, 0)"
    with conn.cursor() as cursor:
        cursor.execute(query, (request.form['fren'], session['username']))
        conn.commit()    
    return redirect(request.url)
        
@app.route('/followers')
@login_required
def seefollowers():
    with conn.cursor() as cursor:
        query = "SELECT username_follower FROM Follow WHERE username_followed = %s AND followstatus = 0"
        cursor.execute(query, (session['username']))
        dataNot = cursor.fetchall()
        query = "SELECT username_follower FROM Follow WHERE username_followed = %s AND followstatus = 1"
        cursor.execute(query, (session['username']))
        dataYes = cursor.fetchall()
    return render_template('followers.html', dataNot=dataNot, dataYes=dataYes )
        
@app.route('/allowfollower', methods=['GET', 'POST'])
@login_required
def allowfollower():
    if request.method != "POST" or "fren" not in request.form:
        return redirect('/')
    query = "UPDATE Follow SET followstatus = 1 WHERE username_followed = %s AND `username_follower` = %s"
    with conn.cursor() as cursor:
        cursor.execute(query, (session['username'],request.form['fren']))
        conn.commit()  
    return redirect('/followers')

@app.route('/viewfollowing', methods=['GET', 'POST'])
@login_required
def viewfollowing():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    if 'fren' in request.form:
        return redirect('/profile/'+request.form['fren'])
    return redirect('/')
 
@app.route('/disownfollower', methods=['GET', 'POST'])
@login_required
def disownfollower():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    query = "UPDATE Follow SET followstatus = 0 WHERE username_followed = %s AND `username_follower` = %s"
    with conn.cursor() as cursor:
        cursor.execute(query, (session['username'],request.form['fren']))
        conn.commit()
    return redirect('/followers')

@app.route('/following')
@login_required
def following():
    if session.get("username") is None:
        return redirect('/')
    with conn.cursor() as cursor:
        query = "SELECT username_followed FROM Follow WHERE username_follower = %s AND followstatus = 0"
        cursor.execute(query, (session['username']))
        dataNot = cursor.fetchall()
        query = "SELECT username_followed FROM Follow WHERE username_follower = %s AND followstatus = 1"
        cursor.execute(query, (session['username']))
        dataYes = cursor.fetchall()
    return render_template('following.html', dataNot=dataNot, dataYes=dataYes )

@app.route('/deletefollow', methods=['GET', 'POST'])
@login_required
def deletefollow():
    
    if request.method != "POST":
        return redirect('/home')
    with conn.cursor() as cursor:
        query = "DELETE FROM Follow  WHERE username_followed = %s AND `username_follower` = %s"
        cursor.execute(query, (request.form['fren'], session['username']))
        conn.commit() 
    return redirect('/following')



#######################
##  Homepage Section ##
#######################
@app.route('/home')
@login_required
def home():
    user = session['username']
    ########Selecting All of "my" photos
    query = '''SELECT *
               FROM Photo where photoPoster = %s'''
    with conn.cursor() as cursor:
        cursor.execute(query, (user))
        data = cursor.fetchall()
    cleanedData = [i for i in data]
    ########Selecting All allfollower=1 photos
    query = '''SELECT *
        FROM Photo
        WHERE allfollowers = 1 
            AND photoposter IN 
            (SELECT username_followed
             FROM Follow
             WHERE username_follower = %s
                AND followstatus = 1) '''
    with conn.cursor() as cursor:
        cursor.execute(query, (user))
        data = cursor.fetchall()
    cleanedData = cleanedData + [i for i in data]
    #######Selecting All photos available to groups im in
    query = '''SELECT * 
        FROM Photo 
        WHERE photoID in
            (SELECT photoID
            FROM SharedWith NATURAL JOIN BelongTo
            WHERE owner_username = groupOwner AND
                  member_username = %s AND
                  photoID not in
                  (SELECT photoID
                    FROM Photo
                    WHERE allfollowers = 1 )) '''
    with conn.cursor() as cursor:
        cursor.execute(query, (user))
        data = cursor.fetchall()
    for i in data:
        if i not in cleanedData:
            cleanedData.append(i)
    
    data=[(i["postingdate"], i) for i in cleanedData]
    data.sort()
    data.reverse()
    cleanedData = [i[1] for i in data]
    
    return render_template('home.html', data=cleanedData)

@app.route('/profile')
@login_required
def myprofile():
    if session.get("username") is None:
        return redirect('/')
    return redirect('/profile/'+session['username'])

@app.route('/profile/<AUserName>')
@login_required
def profileview(AUserName):
    if session.get("username") is None:
        return redirect('/')
    sessionUser = session['username']
    if AUserName == sessionUser:
        
        #All "my" photos
        query = 'SELECT * FROM Photo WHERE photoPoster = %s '
        with conn.cursor() as cursor:
            cursor.execute(query, (AUserName))
            data = cursor.fetchall()
        CD = [(i['postingdate'], i) for i in data]
        CD.sort()
        data = [i[1] for i in CD]
        return render_template('profile.html', data=data, delete=1)
    else:
        
        query = 'SELECT * FROM Follow WHERE username_follower = %s AND username_followed = %s'
        with conn.cursor() as cursor:
            cursor.execute(query, (sessionUser, AUserName))
            data = cursor.fetchall()
        if not data: #If they're not following the requested user
            return render_template('notfollowinguser.html', name=AUserName), 401
        ##This is where we complete the request knowing they have access
        query = '''SELECT *
        FROM Photo
        WHERE allfollowers = 1 
            AND photoposter = %s '''
        with conn.cursor() as cursor:
            cursor.execute(query, (AUserName))
            data = cursor.fetchall()
        ##
        
        query = ''' SELECT * 
        FROM Photo 
        WHERE allfollowers = 0 AND
            photoID in
            (SELECT photoID
            FROM SharedWith NATURAL JOIN BelongTo
            WHERE owner_username = groupOwner AND
                  member_username = %s AND
                  owner_username = %s ) '''
        with conn.cursor() as cursor:
            cursor.execute(query, (sessionUser, AUserName))
            data += cursor.fetchall()
        
        cleandata = [(i["postingdate"],i) for i in data]
        cleandata.sort()
        cleandata.reverse()
        data = [i[1] for i in cleandata]
        return render_template('profile.html', data=data)
    return "OOPS",501


######################
##  Tag, you're it  ##
######################
#/addtags/{{item.photoID}}
@app.route('/addtags/<photoID>')
@login_required
def addtags(photoID,methods=["POST", "GET"]):
    data = None
    with conn.cursor() as cursor:
        query = ''' SELECT * FROM `Photo` 
                    WHERE `photoPoster`=%s AND 
                        `photoID`= %s '''
        cursor.execute(query,(session['username'],photoID))
        data= cursor.fetchall()
    if not data: ##Make sure they own the photo
        return redirect('/profile')
    with conn.cursor() as cursor:
        query = ''' SELECT * FROM Person WHERE username IN
        (
            SELECT username from Tagged WHERE photoID = %s
        ) '''
        cursor.execute(query,(photoID))
        dataYes= cursor.fetchall()
        query = ''' SELECT * FROM Person WHERE username IN 
        (
            SELECT username_follower from Follow 
            WHERE username_followed = %s AND 
                username_follower NOT IN 
               (
                    SELECT username from Tagged WHERE photoID = %s
                )
        )        '''
        cursor.execute(query,(session['username'], photoID))
        dataNot= cursor.fetchall()
    return render_template('addtags.html', dataYes=dataYes, dataNot=dataNot, pid=photoID)

        ##Make the accept tags page and link
@app.route('/tagfollower', methods=['GET', 'POST'])
@login_required
def tagfollower():
    if request.method != "POST" or 'pid' not in request.form or 'fren' not in request.form:
        return redirect('/')
    data = None
    with conn.cursor() as cursor:
        query = ''' SELECT * FROM `Photo` 
                    WHERE `photoPoster`=%s AND 
                        `photoID`= %s '''
        cursor.execute(query,(session['username'],request.form['pid']))
        data= cursor.fetchall()
    if not data: ##Make sure they own the photo
        return redirect('/')
    
    with conn.cursor() as cursor:
        query = ''' SELECT * FROM `Follow` 
                    WHERE `username_followed`=%s AND 
                        `username_follower`= %s AND followstatus = 1 '''
        cursor.execute(query,(session['username'],request.form['fren']))
        data= cursor.fetchall()
    if not data: ##Make sure they only add followers
        return redirect('/addtags/'+request.form['pid'])
    with conn.cursor() as cursor:
            query = '''
                    INSERT INTO `Tagged`(`username`, `photoID`, `tagstatus`) 
                    VALUES (%s, %s, 0)
                    '''
            cursor.execute(query, (request.form['fren'], request.form['pid']))
            conn.commit()
    
    return redirect('/addtags/'+request.form['pid'])

@app.route('/mytags')
@login_required
def mytags():
    with conn.cursor() as cursor:
        query = '''SELECT * FROM Photo where photoID IN 
                    (SELECT photoID FROM Tagged
                    WHERE username = %s AND 
                        tagstatus = 0) '''
        cursor.execute(query,(session['username']))
        data= cursor.fetchall()
    return render_template('mytags.html', data=data)
#/accepttag        
@app.route('/accepttag', methods=['POST'])
@login_required
def accepttag():
    with conn.cursor() as cursor:
        query = '''UPDATE `Tagged` SET `tagstatus`= 1 WHERE `username`=%s AND `photoID`=%s'''
        cursor.execute(query,(session['username'], request.form['pid']))
        conn.commit()
    return redirect('/mytags')


































if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    if len(sys.argv) < 6:
        print("Arguments: db_host db_port db_user db_pass db_dbname db_charset\n")
    else:
        app.run(debug = True)

    