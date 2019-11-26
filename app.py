from flask import Flask, render_template, request, session, url_for, redirect, send_from_directory
import pymysql.cursors
import sys
import os
import hashlib
from datetime import datetime
from werkzeug.utils import secure_filename


app = Flask(__name__)

conn =   pymysql.connect(host       = sys.argv[1],
                           port     = int(sys.argv[2]),
                           user     = sys.argv[3],
                           password = sys.argv[4],
                           db       = sys.argv[5],
                           charset  = sys.argv[6],
                           cursorclass=pymysql.cursors.DictCursor)

@app.route('/')
def index():
    return render_template('index.html')





#####################
##  Login Handler  ##
#####################
#Define route for login
@app.route('/login')
def login():
    if session.get("username") is not None:
        return redirect('/')
    return render_template('login.html')
    
@app.route('/loginAuth', methods=['GET','POST'])
def loginAuth():
    if session.get("username") is not None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/login')
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password']
    #salting password
    saltedPassword = password + salt + username
    hashedpwd = hashlib.sha256(saltedPassword.encode('utf-8')).hexdigest()
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s and password = %s'
    cursor.execute(query, (username, hashedpwd))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['username'] = username
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login credentials'
        return render_template('login.html', error=error)

############################
##  Registration Handler  ##
############################
salt = "d1f4aa2ca12aefa18e25628ba680e81f"
#Define route for register
@app.route('/register')
def register():
    if session.get("username") is not None:
        return redirect('/')
    return render_template('register.html')

#Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    if session.get("username") is not None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/register')
    #grabs information from the forms
    username = request.form['username']
    
    password = request.form['password']
    saltedPassword = password + salt + username
    hashedpwd = hashlib.sha256(saltedPassword.encode('utf-8')).hexdigest()
    
    fname = request.form['fname']
    lname = request.form['lname']
    bio   = request.form['bio']
    
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    #stores the results in a variable
    data = cursor.fetchone()
    
    #use fetchall() if you are expecting more than 1 data row
    error = None
    if(data):
        #If the previous query returns data, then user exists
        error = "This user already exists"
        cursor.close()
        return render_template('register.html', error = error)
    elif len(username) > 20:
        error = "Username is too long, please pick one that is 20 characters or less"
        cursor.close()
        return render_template('register.html', error = error)
    else:
        ins = 'INSERT INTO Person VALUES(%s, %s, %s, %s, %s)'
        cursor.execute(ins, (username, hashedpwd, fname, lname, bio))
        conn.commit()
        cursor.close()
        return render_template('index.html')



#####################
##  Logout Section ##
#####################
@app.route('/logout')
def logout():
    if session.get("username") is None:
        return redirect('/')
    session.pop('username')
    return redirect('/')



#######################
##  Photo Management ##
#######################
@app.route('/reaper')
def reapin():
    return redirect('/favicon.ico')

def has_permission(photoID, username):
    return 1
    cursor = conn.cursor()
    query = "SELECT filepath FROM Photo WHERE photoID = %s "
    cursor.execute(query, (photoID))
    data = cursor.fetchone()
    
    if data['allFollowers']:
        poster=data['photoPoster']
        query = "SELECT * FROM Follow WHERE username_follower = %s AND username_followed = %s"
        cursor.execute(query, (username, poster))
        data = cursor.fetchone() 
        
        if data :
            cursor.close()
            return True
    else:
        query = """SELECT * from Photo WHERE photoID = %s AND
                    (photoID in
                           (SELECT photoID FROM SharedWith NATURAL JOIN BelongTo
                              WHERE groupOwner = owner_username and
                                    member_username = %s) )"""
        cursor.execute(query, (photoID, username, username))
        data = cursor.fetchone() 
        
        if data:
            cursor.close()
            return True
    cursor.close()
    return False
    
@app.route('/reaper/<photoID>')
def reapergetter(photoID):
    if session.get("username") is None:
        return redirect('/')
    if has_permission(photoID, session['username']):
        cursor = conn.cursor()
        query = "SELECT filepath FROM Photo WHERE photoID = %s "
        cursor.execute(query, (photoID))
        data = cursor.fetchone()
        head_tail = os.path.split(data['filepath'])
        cursor.close()
        return send_from_directory(head_tail[0], head_tail[1])
        
    else:
        return send_from_directory(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static'), "ERROR.png")
@app.route('/removephoto', methods=['GET','POST'])
def removephototo():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    if "pid" not in request.form:
        return "No", 418
    photoID = request.form['pid']
    cursor = conn.cursor()
    query = "SELECT * FROM Photo WHERE photoPoster = %s AND photoID = %s "
    cursor.execute(query, (session['username'], photoID))
    data = None
    data = cursor.fetchone()
    if not data:
        cursor.close()
        return "No", 418
    query = "DELETE FROM SharedWith WHERE groupOwner = %s AND photoID = %s"
    cursor.execute(query, (session['username'], photoID))
    query = "DELETE FROM Photo WHERE photoPoster = %s AND photoID = %s"
    cursor.execute(query, (session['username'], photoID))
    conn.commit()
    cursor.close()
    return redirect( '/profile' )
        


#######################
##  Homepage Section ##
#######################
@app.route('/home')
def home():
    if session.get("username") is None:
        return redirect('/')
    user = session['username']
    cursor = conn.cursor()
    ########Selecting All of "my" photos
    query = '''SELECT *
               FROM Photo where photoPoster = %s'''
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
    cursor.execute(query, (user))
    data = cursor.fetchall()
    for i in data:
        if i not in cleanedData:
            cleanedData.append(i)
    
    data=[(i["postingdate"], i) for i in cleanedData]
    data.sort()
    data.reverse()
    cleanedData = [i[1] for i in data]
    cursor.close()
    return render_template('home.html', data=cleanedData)

@app.route('/profile')
def myprofile():
    if session.get("username") is None:
        return redirect('/')
    return redirect('/profile/'+session['username'])

@app.route('/profile/<AUserName>')
def profileview(AUserName):
    if session.get("username") is None:
        return redirect('/')
    sessionUser = session['username']
    if AUserName == sessionUser:
        cursor = conn.cursor();
        #All "my" photos
        query = 'SELECT * FROM Photo WHERE photoPoster = %s '
        cursor.execute(query, (AUserName))
        data = cursor.fetchall()
        CD = [(i['postingdate'], i) for i in data]
        CD.sort()
        data = [i[1] for i in CD]
        cursor.close()
        return render_template('profile.html', data=data, delete=1)
    else:
        cursor = conn.cursor();
        query = 'SELECT * FROM Follow WHERE username_follower = %s AND username_followed = %s'
        cursor.execute(query, (sessionUser, AUserName))
        data = cursor.fetchall()
        if not data: #If they're not following the requested user
            return render_template('notfollowinguser.html', name=AUserName), 401
        ##This is where we complete the request knowing they have access
        cursor.close()
        return "OOPS",501
    return "OOPS",501

############################
##  Find Friends Handler  ##
############################
@app.route('/searchfriends', methods=['GET', 'POST'])
def searchfriends():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "SELECT username FROM Person WHERE username LIKE %s"
    cursor.execute(query, ("%"+request.form['fren']+"%"))
    #stores the results in a variable
    data = cursor.fetchall()
    return render_template('browsefriends.html', data=data)

@app.route('/addfollower', methods=['GET', 'POST'])
def addfollower():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "INSERT INTO Follow(username_followed, username_follower, followstatus) VALUES (%s, %s, 0)"
    cursor.execute(query, (request.form['fren'], session['username']))
    conn.commit()
    cursor.close()    
    return redirect(request.url)
        
@app.route('/followers')
def seefollowers():
    if session.get("username") is None:
        return redirect('/')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "SELECT username_follower FROM Follow WHERE username_followed = %s AND followstatus = 0"
    cursor.execute(query, (session['username']))
    dataNot = cursor.fetchall()
    cursor.close() 
    cursor = conn.cursor()
    query = "SELECT username_follower FROM Follow WHERE username_followed = %s AND followstatus = 1"
    cursor.execute(query, (session['username']))
    dataYes = cursor.fetchall()
    cursor.close()    
    return render_template('followers.html', dataNot=dataNot, dataYes=dataYes )
        
@app.route('/allowfollower', methods=['GET', 'POST'])
def allowfollower():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "UPDATE Follow SET followstatus = 1 WHERE username_followed = %s AND `username_follower` = %s"
    cursor.execute(query, (session['username'],request.form['fren']))
    conn.commit()
    cursor.close()    
    return redirect('/followers')

@app.route('/viewfollowing', methods=['GET', 'POST'])
def viewfollowing():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    if 'fren' in request.form:
        return redirect('/profile/'+request.form['fren'])
    return redirect('/')
 
@app.route('/disownfollower', methods=['GET', 'POST'])
def disownfollower():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "UPDATE Follow SET followstatus = 0 WHERE username_followed = %s AND `username_follower` = %s"
    cursor.execute(query, (session['username'],request.form['fren']))
    conn.commit()
    cursor.close()    
    return redirect('/followers')

@app.route('/following')
def following():
    if session.get("username") is None:
        return redirect('/')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "SELECT username_followed FROM Follow WHERE username_follower = %s AND followstatus = 0"
    cursor.execute(query, (session['username']))
    dataNot = cursor.fetchall()
    cursor.close() 
    cursor = conn.cursor()
    query = "SELECT username_followed FROM Follow WHERE username_follower = %s AND followstatus = 1"
    cursor.execute(query, (session['username']))
    dataYes = cursor.fetchall()
    cursor.close()    
    return render_template('following.html', dataNot=dataNot, dataYes=dataYes )

@app.route('/deletefollow', methods=['GET', 'POST'])
def deletefollow():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/home')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "DELETE FROM Follow  WHERE username_followed = %s AND `username_follower` = %s"
    cursor.execute(query, (request.form['fren'], session['username']))
    conn.commit()
    cursor.close()    
    return redirect('/following')

##########################
##  Post Photo Handler  ##
##########################

dir_path = os.path.dirname(os.path.realpath(__file__))
imagesFolder = os.path.join(dir_path, "user_files", "")
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

@app.route('/postphoto')
def postphoto():
    if session.get("username") is None:
        return redirect('/')
    return render_template('postphoto.html')

@app.route('/postsubmit', methods=['GET', 'POST'])
def submitphoto():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/postphoto')
    if request.files:
        image = request.files["image"]
        if image.filename == "":
            return redirect("/postphoto",error="File Had No Name")
        if not allowed_image(image.filename):
            return redirect("/postphoto",error="Invalid Filetype")
        filename = secure_filename(image.filename)
        filepath = os.path.join(imagesFolder, session['username']+"."+filename)
        #cursor used to send queries
        all=0
        if "all" in request.form:
            all=1
        cursor = conn.cursor()
        #executes query
        query = "INSERT INTO Photo ( postingdate, filepath, allFollowers, caption, photoPoster) VALUES( %s, %s, %s, %s, %s)"
        cursor.execute(query, (datetime.now(),
                        filepath,
                        all,
                        request.form["caption"],
                        session['username']))
        conn.commit()
        cursor.close()
        image.save(filepath)
        if "all" not in request.form:
            return redirect("/pickGroups")
        return redirect('/home')
    return render_template('postphoto.html')

@app.route('/pickGroups')
def pickgroups():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        #cursor used to send queries
        cursor = conn.cursor()
        #executes query
        query = "SELECT photoID FROM Photo  WHERE photoPoster = %s and postindate = (select max(postingdate) from photo where photoposter = %s)"
        cursor.execute(query, (session['username'], session['username']))
        photoID = cursor.fetchone().photoID
        cursor.close()   
    else:
        if "photo" in request.form:
            photoID = request.form['photo']
        else:
            redirect ('/submitphoto')
    #get list of groups 
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "SELECT groupName, description FROM Friendgroup WHERE groupOwner = %s"
    cursor.execute(query, (session['username']))
    data = cursor.fetchall()
    cursor.close() 
    #allow user to select mygroups
    
    
    
########################
##  Group Management  ##
########################
@app.route('/mygroups')
def mygroups():
    if session.get("username") is None:
        return redirect('/')
    cursor = conn.cursor()
    #executes query
    query = "SELECT groupName, description FROM Friendgroup WHERE groupOwner = %s"
    cursor.execute(query, (session['username']))
    data = cursor.fetchall()
    cursor.close() 

    return render_template('mygroups.html', data = data)

@app.route('/makegroup', methods=['GET', 'POST'])
def makegroup():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "INSERT INTO Friendgroup(groupOwner, groupName, description) VALUES (%s, %s, %s)"
    cursor.execute(query, (session['username'], request.form['groupname'], request.form['desc']))
    conn.commit()
    cursor.close()    
    return redirect('/mygroups')

@app.route('/modifygroup', methods=['GET', 'POST'])
def modifygroup():
    if session.get("username") is None:
        return redirect('/')
    if request.method != "POST":
        return redirect('/')
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = "INSERT INTO Friendgroup(groupOwner, groupName, description) VALUES (%s, %s, %s)"
    cursor.execute(query, (session['username'], request.form['groupname'], request.form['desc']))
    conn.commit()
    cursor.close()    
    return redirect('modifygroup.html')



@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
app.secret_key = '''5d1f4aa2ca12aefa18e25628ba680e81f2fb1f
                    7dde78c174396228cc3170285e8a459037bb21
                    a375b939d6e82d5f0aba2bdec389c610fae299
                    428f3197ca3921c2c00c59fa1ceb1417cc142a
                    d763826be48983e4a96aed96436c621b9809e2
                    d58b309a94ab9dfd1769647ec6fd5d90821c40
                    Yes, the spaces are part of the key'''

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Arguments: db_host db_port db_user db_pass db_dbname db_charset\n")
    else:
        app.run(debug = True)