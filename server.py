from flask import Flask, request, redirect
import random

app = Flask(__name__)

nextID = 4
topics = [
    {'id':1, 'title':'html', 'body' :'html is ...'},
    {'id':2, 'title':'css', 'body' :'css is ...'},
    {'id':3, 'title':'javascript', 'body' :'javascript is ...'}
]

def template(contents, content):
    return f'''<!doctype html>
    <html>
     <head><title>welcome</title></head>
         <body>
             <h1>Hi</h1>
                <h2><a href="/">WEB</a></h2>
                    <ul>
                        {contents}
                    </ul>
                    {content}
                    <a href="/create/">create</a>
         </body>
    </html>
    '''

def getContents():
    liTags = ''
    for topic in topics:
        liTags += f'<li><a href="/user/{topic["id"]}/">{topic["title"]}</a></li>'
    return liTags

@app.route('/')
def index():

    return template(getContents(),'<h2>Welcome</h2> Hello, Web' )

@app.route('/user/<int:id>/')
def userID(id):

    title = ''
    body = ''

    for topic in topics:
        if id == topic['id']:
            title = topic['title']
            body = topic['body']
            break
    print(title, body)
    return template(getContents(), f'<h2>{title}</h2>{body}' )

@app.route('/create/', methods=['GET', 'POST'])
def create():
    if request.method == 'GET':
        content = '''
                <form action="/create/" method="POST">
                    <p><input type="text" name="title" placeholder="title"></p>
                    <p><textarea name="body" placeholder="body"></textarea></p>
                  <p><input type="submit" value="create"></p>
                </form>
        '''
        return template(getContents(), content)
    elif request.method == 'POST':
        global nextID
        title = request.form['title']
        body = request.form['body']
        newTopic = {'id':nextID, 'title':title, 'body':body}
        topics.append(newTopic)
        url = '/user/'+ str(nextID) + '/'
        nextID += 1
        return redirect(url)

@app.route('/wait/')
def wait():
    
    return f'''
        <html>
        <head> Hidden Meta Tag </head>
        <body>
            <h1> 'Hello' </h1>
        
        </body>
        </html>
    '''

if __name__ == '__main__':
    app.run(port=5000, debug=True)