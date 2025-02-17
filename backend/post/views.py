from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import messages
from allModels.models import Posts, Comments, Likes, Liked, Shares
from allModels.models import Authors, Followers, FollowRequests
from rest_framework.response import Response
from django.urls import reverse
from django.contrib.auth.decorators import login_required
import uuid
from django.db.models import Q
from allModels.models import Inbox, Node
import requests
from requests.auth import HTTPBasicAuth
import base64
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework import permissions, authentication
from django.forms.models import model_to_dict
from django.http import JsonResponse
import json
from django.views import View
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.core.files.base import ContentFile
from .serializers import AuthorSerializer, PostsSerializer, LikedSerializer, CommentSerializer, FollowRequestSerializer, ShareSerializer

def get_image(image_url):
    '''
    This function is used to convert received image url to base64
    '''
    #get image type
    img_type = str(image_url).split(".")[-1]
    #get image path
    try:
        imagePath = '.' + str(image_url)
    except:
        return Response(status=404)
    #convert image to base64
    with open(imagePath, 'rb') as img:
        image_data = img.read()

    base64_encoded_image = base64.b64encode(image_data).decode('utf-8')

    result =  f'data:image/{img_type};base64,{base64_encoded_image}'

    return result

create_post_example = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'title': openapi.Schema(type=openapi.TYPE_STRING, example='Sample Title', description='Title is required'),
        'description': openapi.Schema(type=openapi.TYPE_STRING, example='Sample Description'),
        'content': openapi.Schema(type=openapi.TYPE_STRING, example='Sample Content', description='Content is required'),
        'visibility': openapi.Schema(type=openapi.TYPE_STRING, example='PUBLIC'),
        'content_type': openapi.Schema(type=openapi.TYPE_STRING, example='text/plain'),
        'categories': openapi.Schema(type=openapi.TYPE_STRING, example='Category1, Category2'),
        'contentImage': openapi.Schema(type=openapi.TYPE_FILE, example='image.png', description='Image is optional(image post or text post)'),
    },
    required=['title', 'visibility','description'],
)

@swagger_auto_schema(method='post', operation_description="Create a new post.", request_body=create_post_example)
@swagger_auto_schema(method='get', operation_description="Don't use this get, this is just for testing.")
@api_view(['GET', 'POST'])
def create_post(request, userId):
    '''
    This function is used to create a new post and in the same time share the post to all followers of the author(except private post)
    '''
    if request.method == 'POST':
        #get info from request
        title = request.data.get('title')
        if "description" in request.data:
            description = request.data.get('description')
        else:
            description = ""
        if "content" in request.data:
            content = request.data.get('content')
        else:
            content = ""
        if "visibility" in request.data:
            visibility = request.data.get('visibility')
        else:
            visibility = "PUBLIC"
        if "content_type" in request.data:
            content_type = request.data.get('content_type')
        else:
            content_type = "text/plain"
        if "categories" in request.data:
            categories = request.data.get('categories')
        else:
            categories = ""
        uid = str(uuid.uuid4())
        #decode image
        tempCheck = 0
        if content_type == "image":  
            tempCheck = 1
            image_data = request.data.get('contentImage')
            if image_data:
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                decoded_image = ContentFile(base64.b64decode(imgstr), name=f'{uid}.{ext}')
                contentImage = decoded_image
            else:
                contentImage = ""
                
        #create a new post
        new_post = Posts()
        new_post.title = title
        new_post.description = description
        if tempCheck == 1:
            new_post.contentImage = contentImage
        else:
            new_post.content = content
        new_post.visibility = visibility
        new_post.contentType = content_type
        new_post.uuid = uid
        #create post id for the new post
        new_post.id = f"{request.build_absolute_uri('/')[:-1]}/service/authors/{str(userId)}/posts/{uid}"
        if "source" in request.data:
            new_post.source = request.data.get('source')
        else:
            new_post.source = new_post.id
        if "origin" in request.data:
            new_post.origin = request.data.get('origin')
        else:
            new_post.origin = new_post.id
        current_author = Authors.objects.get(uuid=userId)
        new_post.author = current_author
        new_post.categories = categories
        new_post.count = "0"
        new_post.save()

        #get all followers of the author
        current_author_followers = Followers.objects.filter(followedUser=current_author)
        #share the post to all followers of the author(except private post)
        if current_author_followers and (new_post.visibility!="PRIVATE" and new_post.visibility!="private"):
            all_node = Node.objects.all()
            #loop through all followers
            for item in current_author_followers:
                #check if the follower is remote
                if item.follower.uuid == item.follower.username:
                    #get uuid of the follower
                    uuuid = item.follower.url.split('/')[-1]
                    host = item.follower.host
                    #loop through all nodes to find the node that the follower is in
                    for node in all_node:
                        temp_node = str(node.host).replace("/service","")
                        #check if the node is the node that the follower is in, if yes, take nessary data and send the post to the follower
                        if str(host) == temp_node:
                            inbox_url = f"{str(node.host)}/authors/{str(uuuid)}/inbox/"
                            send_author = AuthorSerializer(current_author)
                            send_post = PostsSerializer(new_post)
                            
                            comment = send_post.data['id'] + "/comments"
                            #if is image post, get the image type and encode the image
                            if send_post.data['contentType'] == "image":
                                image_type = new_post.contentImage.url.split('.')[-1]

                                if image_type == "png":
                                    types = "image/png;base64"

                                elif image_type == "jpg":
                                    types = "image/jpeg;base64"
                                
                                image_code = get_image(new_post.contentImage.url)
                              
                            else:
                                types = send_post.data['contentType']
                                image_code = send_post.data["contentImage"]
                            
                            if send_post.data['content'] == "" or send_post.data['content'] == None:
                                contents = image_code
                            else:
                                contents = send_post.data['content']
                            send_data = {
                                "type": "post",
                                "title": send_post.data['title'],
                                "id": send_post.data['id'],
                                "source": send_post.data['source'],
                                "origin": send_post.data['origin'],
                                "description": send_post.data['description'],
                                "contentType": types,
                                "content": contents,
                                "author": send_author.data,
                                "comments": comment,
                                "published": send_post.data['published'],
                                "visibility": send_post.data['visibility'],
                                "unlisted": "false",
                            }

                            #send the post to the follower with the inbox url
                            try:
                                response = requests.post(inbox_url, data=send_data, auth=HTTPBasicAuth(str(node.username),str(node.password)))
                                break
                                if response.status_code !=200 or response.status_code !=201:
                                    return Response({"response ":f"{response.status_code} {response.reason} {response.text}"}, status=404)
                                break
                            except Exception as e:
                                break
                                print(e)
                                return Response({"message": "Create post send to follower's inbox raise error"}, status=404) 

                else: 
                    #send to local follower
                    try:
                        
                        follower = item.follower
                        follower_inbox = Inbox.objects.get(author=follower)
                        new_share = Shares.objects.create(author=current_author, post=new_post)
                        follower_inbox.posts.add(new_share)
                        follower_inbox.save()
                    except Exception as e:
                        break
                        print(e)
                        return Response({"message": "Create post send to follower's inbox raise error"}, status=404)

        return Response({"message": "Create post done"},status=201)
    else:
        responseData = {
            "type": "creat post",
            "items": '[]'
        }
        return Response(responseData, status=200)


create_comment_example = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'comment': openapi.Schema(type=openapi.TYPE_STRING, description='Comment text', example='This is a sample comment.'),
        'content_type': openapi.Schema(type=openapi.TYPE_STRING, description='Content type of the comment', example='text/plain'),
    },
    required=['comment']
)

@swagger_auto_schema(method='post', operation_description="Create a new comment on the specified post.", request_body=create_comment_example)

@api_view(['POST'])
def create_comment(request, userId, postId):
    '''
    create a new comment on the specified post
    '''
    if request.method == 'POST':
        comment = request.data.get('comment')
        content_type = request.data.get('content_type', 'text/plain')
        uid = str(uuid.uuid4())

        newComment = Comments()
        newComment.comment = comment
        newComment.contentType = content_type
        newComment.uuid = uid
        newComment.id = f"{request.build_absolute_uri('/')[:-1]}/service/authors/{str(userId)}/posts/{str(postId)}/comments/{uid}"
        
        currentAuthor = Authors.objects.get(uuid=userId)
        newComment.author = currentAuthor

        currentPost = Posts.objects.get(uuid=postId)
        newComment.post = currentPost
        newComment.save()

        # Increment the post count and save the post
        currentPost.count = str(int(currentPost.count) + 1)
        currentPost.save()

        # comment added to post author's inbox
        post_author = Posts.objects.get(uuid=postId).author
        post_author_inbox = Inbox.objects.get(author=post_author)
        post_author_inbox.comments.add(newComment)
        post_author_inbox.save()

        responseData = {
            "type": "creat comment",
            "items": model_to_dict(newComment)
        }

        return Response(responseData,status=201)

    else:
        responseData = {
            "type": "creat comment",
            "items": '[]'
        }
        return Response(responseData, status=200)

@swagger_auto_schema(method='post', operation_description="Create a like to specified post, no data required.")

@api_view(['POST'])
def create_like(request, userId, postId):
    '''
    create a like to specified post
    '''
    if request.method == 'POST':
        post = Posts.objects.get(uuid=postId).id
        currentAuthor = Authors.objects.get(uuid=userId)
        author_name = currentAuthor.displayName
        summary = author_name + " Likes your post"
        # check if the like already exists
        if not Likes.objects.filter(author=currentAuthor, summary=summary, object=post):
            # create a new like
            context = f"{request.build_absolute_uri('/')[:-1]}/service/authors/{str(userId)}/posts/{str(postId)}/likes"
            like = Likes.objects.create(context=context,author=currentAuthor, summary=summary, object=post)
            like.save()
            if not Liked.objects.filter(object=post):
                receiver_liked = Liked.objects.create(object=post)
            liked = Liked.objects.get(object=post)
            liked.items.add(like)

            # Liked added to post author's inbox
            post_author = Posts.objects.get(uuid=postId).author
            post_author_inbox = Inbox.objects.get(author=post_author)
            post_author_inbox.likes.add(like)
            post_author_inbox.save()

            responseData = {
                    "type": "creat like",
                    "items": model_to_dict(like)
                }
        else:
            responseData = {
                    "type": "creat like exists",
                    "items": '[]'
                }

        return Response(responseData,status=201)

    else:
        responseData = {
            "type": "creat like",
            "items": '[]'
        }
        return Response(responseData, status=200)

share_post_example = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'sendTo': openapi.Schema(type=openapi.TYPE_STRING, description='author uuid want receive this share', example='4e456d55-295b-4a9f-9eh1-3c71732e9f5e'),
    },
    required=['sendTo']
)

@swagger_auto_schema(method='post', operation_description="Share post from current author to another author.", request_body=share_post_example)
@api_view(['POST'])
def share_post(request, userId, postId):
    '''
    share post from current author to another author, add to their inbox
    '''
    # get current author and post
    currentAuthor = Authors.objects.get(uuid=userId)
    selectedPost = Posts.objects.get(uuid=postId)

    if request.method == 'POST':
        sendTo = request.data.get('sendTo')
        sendToAuthor = Authors.objects.get(uuid=sendTo)

        inbox = Inbox.objects.get(author=sendToAuthor)
        # create a new share to store in inbox
        newShare = Shares.objects.create(post=selectedPost, author=currentAuthor)
        newShare.save()

        inbox.posts.add(newShare)
        inbox.save()

        responseData = {
                    "type": "successfully shared",
                    "items": "[]"
                }

        return Response(responseData,status=201)

    else:
        responseData = {
            "type": "share post",
            "items": '[]'
        }
        return Response(responseData, status=200)

@swagger_auto_schema(method='post', operation_description="Create a like to specified comment under specified post, no data required.")

@api_view(['POST'])
def create_like_comment(request, userId, postId, commentId):
    '''
    create a like to specified comment under specified post
    '''
    if request.method == 'POST':
        comment = Comments.objects.get(uuid=commentId)
        comment_author = comment.author
        currentAuthor = Authors.objects.get(uuid=userId)
        summary = currentAuthor.displayName + " Likes your comment"
        obj = comment.id
        # check if the like already exists
        if not Likes.objects.filter(author=currentAuthor, summary=summary, object=obj):
            context = f"{request.build_absolute_uri('/')[:-1]}/service/authors/{str(userId)}/comments/{str(commentId)}/likes"
            like = Likes.objects.create(context=context, author=currentAuthor, summary=summary, object=obj)
            like.save()
            if not Liked.objects.filter(object=obj):
                receiver_liked = Liked.objects.create(object=obj)
            liked = Liked.objects.get(object=obj)
            liked.items.add(like)

            # Liked added to inbox
            comment_author = Comments.objects.get(uuid=commentId).author
            comment_author_inbox = Inbox.objects.get(author=comment_author)
            comment_author_inbox.likes.add(like)
            comment_author_inbox.save()

            responseData = {
                    "type": "creat comment like",
                    "items": model_to_dict(like)
                }

        else:
            responseData = {
                    "type": "creat comment like exists",
                    "items": '[]'
                }

        return Response(responseData,status=201)

    else:
        responseData = {
            "type": "creat comment like",
            "items": '[]'
        }
        return Response(responseData, status=200)
    

