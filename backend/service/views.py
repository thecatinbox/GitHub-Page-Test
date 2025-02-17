from django.shortcuts import render
from django.http import HttpResponseRedirect, FileResponse, Http404, HttpResponseBadRequest
from django.urls import reverse
from rest_framework.response import Response
from rest_framework import permissions, authentication
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view, permission_classes, authentication_classes, renderer_classes
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from .serializers import AuthorSerializer, PostsSerializer, LikedSerializer, CommentSerializer, FollowRequestSerializer, ShareSerializer
from allModels.models import Authors, Followers, FollowRequests
from allModels.models import Posts, Comments, Likes, Liked, Shares
from allModels.models import Inbox, Node
from rest_framework.permissions import AllowAny
import uuid
import base64
from itertools import chain
from django.http import JsonResponse
from django.views import View
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import requests
from requests.auth import HTTPBasicAuth
import json
import os
from django.core.files.base import ContentFile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_image(image_url):
    '''
    use image url to get image data and return base64 encoded image
    '''
    #get image type
    img_type = str(image_url).split(".")[-1]
    #get image path
    try:
        imagePath = '.' + str(image_url)
    except:
        return Response(status=404)
    #read image data and encode it
    with open(imagePath, 'rb') as img:
        image_data = img.read()

    base64_encoded_image = base64.b64encode(image_data).decode('utf-8')

    result =  f'data:image/{img_type};base64,{base64_encoded_image}'

    return result

def getURLId(url):
    return url.split('/')[-1]


def paginate(request,objects):
    """
    paginates a list of objects.
    """
    page=1
    page_size=10
    start_index = page * page_size - page_size
    end_index = page * page_size

    objects = objects[start_index:end_index]
    
    return objects


@swagger_auto_schema(method='get', operation_description="Get all authors' informations.")
@api_view(['GET'])
def authorsList(request):
    """
    Read and return all authors in the database as a list
    """
    #use to identify authors belong to this server
    authors1 = Authors.objects.filter(url__icontains="https://cmput404-project-data.herokuapp.com")#change when different deployment
    authors2 = Authors.objects.filter(url__icontains="http://127.0.0.1")
    authors = list(chain(authors1,authors2))


    paginated_authors = paginate(request,authors)
    if not paginated_authors:
        return Response(status=404)

    itemsList = []
    for item in paginated_authors:
        dict = {}
        serializer = AuthorSerializer(item)
        data = serializer.data

        for k, v in data.items():
            dict[k] = v

        dict['displayName'] = data['displayName']
        #get image data and encode it
        img = item.profileImage.url if item.profileImage else None
        if img:
            dict['profileImage'] = get_image(img)
        else:
            dict['profileImage'] = None

        itemsList.append(dict)

    responseData = {
        "type": "authors",
        "items": itemsList,
    }

    return Response(responseData, status=200)


singleAuthor_example = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'github': openapi.Schema(type=openapi.TYPE_STRING, description='Github URL'),
        'profileImage': openapi.Schema(type=openapi.TYPE_STRING, description='Profile Image URL'),
        'host': openapi.Schema(type=openapi.TYPE_STRING, description='Host URL'),
        'url': openapi.Schema(type=openapi.TYPE_STRING, description='Author URL'),
    },
    required=['github', 'profileImage', 'host', 'url'],
)
@swagger_auto_schema(method='post', operation_description="Modify author's information.", request_body=singleAuthor_example)
@swagger_auto_schema(method='get', operation_description="Get informations for specific author.")
@api_view(['GET', 'POST'])
def singleAuthor(request, pk):
    """
    This view returns a single author's information or modify the author's information.
    """
    #get author by id if not exist return 404
    try:
        author = Authors.objects.get(uuid=pk)
    except Authors.DoesNotExist:
        return Response(status=404)
    #get author's information and return it
    if request.method == 'GET':
        serializer = AuthorSerializer(author)
        data = serializer.data
        data['displayName'] = data.pop('displayName')
        #get image data and encode it
        img = author.profileImage.url if author.profileImage else None
        if img:
            data['profileImage'] = get_image(img)
        else:
            data['profileImage'] = None
        responseData = {
            "type": "authors",
            "items": data
        }
        return Response(responseData, status=200)
    #modify author's information
    elif request.method == 'POST':
        #check if modify info provided and modify it
        author.github = request.data.get('github', author.github)
        author.displayName = request.data.get('displayName', author.displayName)
        uid = str(uuid.uuid4())
        if request.data.get('profileImage'):
            profileImage_data = request.data.get('profileImage')
            if profileImage_data:
                format, imgstr = profileImage_data.split(';base64,')
                ext = format.split('/')[-1]
                decoded_image = ContentFile(base64.b64decode(imgstr), name=f'{uid}.{ext}')
                profileImage = decoded_image
                author.profileImage = profileImage

        author.host = request.data.get('host', author.host)
        author.url = request.data.get('url', author.url)
        author.save()
        return Response(status=200)
    
@swagger_auto_schema(method='get', operation_description="Get the author's github link.")
@api_view(['GET'])
def showGithubActivity(request, pk):
    """
    This view is used to return one author's Github activity
    """
    #get author by id if not exist return 404
    try:
        author = Authors.objects.get(uuid=pk)
    except Authors.DoesNotExist:
        return Response(status=404)
    
    #get author's github activity
    if request.method == 'GET':
        serializer = AuthorSerializer(author)
        data = serializer.data

        # Extract GitHub username from profile URL
        github_url = data['github']
        username = github_url.split("/")[-1]
                           
        # Set up OAuth session
        with open(os.path.join(BASE_DIR, 'service/github_token.txt'), 'r') as f:
            token = f.read().strip()
        oauth = requests.Session()
        oauth.auth = (token, '')

        # Make a request to the GitHub API rate limit endpoint to get the current rate limit information
        rate_limit_response = oauth.get('https://api.github.com/rate_limit')

        # Extract the remaining requests count from the rate limit information
        rate_limit_data = json.loads(rate_limit_response.content)
        remaining_requests = rate_limit_data['resources']['core']['remaining']

        # Use access token to make API request to retrieve GitHub activity data
        endpoint_url = f"https://api.github.com/users/{username}/events/public"
        response = oauth.get(endpoint_url)

        if response.status_code == 200:
            activity_data = json.loads(response.content)

            # Format the response as a JSON file
            responseData = {
                "type": "author",
                "remaining_requests":remaining_requests,
                "github_activity": activity_data
            }

            return Response(responseData, status=200)
        else:
            return Response(status=response.status_code)
   

@swagger_auto_schema(method='get', operation_description="Get all public posts.")
@api_view(['GET'])
def getAllPublicPosts(request):
    """
    This view is used to return all public posts from this server.
    """
    #identify the posts that are public and from this server
    posts1 = Posts.objects.filter(visibility='PUBLIC', id__icontains="https://cmput404-project-data.herokuapp.com").prefetch_related('author')#change when different deployment
    posts2 = Posts.objects.filter(visibility='PUBLIC', id__icontains="http://127.0.0.1").prefetch_related('author')#change when different deployment
    posts = list(chain(posts1, posts2))
    items_list = []
    #for all valid public posts get the data and return it
    for post in posts:
        #get post image data and encode it
        the_image = post.contentImage.url if post.contentImage else None
        if the_image:
            the_image = get_image(the_image)
        #get author image data and encode it
        the_author_image = post.author.profileImage.url if post.author.profileImage else None
        if the_author_image:
            the_author_image = get_image(the_author_image)
        data = PostsSerializer(post).data
        author_data = AuthorSerializer(post.author).data
        author_data['displayName'] = author_data.pop('displayName')
        categories = data.pop('categories')
        comments_count = data.pop('count')
        
        if data['contentImage']:
            data['contentImage'] = str(the_image)
        else:
            data['contentImage'] = None

        if post.author.profileImage:
            author_data['profileImage'] = str(the_author_image)
        else:
            author_data['profileImage'] = None

        item = {
            **data,
            'author': author_data,
            'categories': categories,
            'count': comments_count,
        }
        items_list.append(item)

    response_data = {
        "type": "posts",
        "items": items_list
    }

    return Response(response_data, status=200)

Post_example = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'title': openapi.Schema(type=openapi.TYPE_STRING, description='Title of the post'),
        'source': openapi.Schema(type=openapi.TYPE_STRING, description='Source of the post'),
        'origin': openapi.Schema(type=openapi.TYPE_STRING, description='Origin of the post'),
        'description': openapi.Schema(type=openapi.TYPE_STRING, description='Description of the post'),
        'contentType': openapi.Schema(type=openapi.TYPE_STRING, description='Content type of the post'),
        'content': openapi.Schema(type=openapi.TYPE_STRING, description='Content of the post'),
        'categories': openapi.Schema(type=openapi.TYPE_STRING, description='Categories of the post'),
        'visibility': openapi.Schema(type=openapi.TYPE_STRING, description='Visibility of the post'),
    },
    required=['title', 'source', 'origin', 'description', 'contentType', 'content', 'categories', 'visibility'],
)


@swagger_auto_schema(method='get', operation_description="Get posts create by specific author.")
@api_view(['GET'])
def Post(request, pk):
    """
    This view is used to get posts of a given author
    """

    if request.method == 'GET':
        item_list = []
        #get the author and serialize it
        author = Authors.objects.get(uuid=pk)
        serializeAuthor = AuthorSerializer(author)
        #get all posts of the author
        try:     
            posts = Posts.objects.filter(author=author)
            posts = paginate(request, posts)
            

            if not posts:
                responseData = {
                    "type": "posts",
                    "items": item_list
                }
                print(responseData)
                return Response(responseData, status=200)
            #for each post get the data and return it
            for item in posts:
                data = PostsSerializer(item).data
                author_data = AuthorSerializer(item.author).data
                author_data['displayName'] = author_data.pop('displayName')
                categories = data.pop('categories')
                comments_count = data.pop('count')
                #get post image data and encode it
                if data['contentImage']:
                    img = item.contentImage.url if item.contentImage else None
                    if img:
                        data['contentImage'] = get_image(img)
                    else:
                        data['contentImage'] = None
                else:
                    data['contentImage'] = None
                #get author image data and encode it
                if item.author.profileImage:
                    img2 = item.author.profileImage.url if item.author.profileImage else None
                    if img2:
                        author_data['profileImage'] = get_image(img2)
                    else:
                        author_data['profileImage'] = None
                else:
                    author_data['profileImage'] = None
                
            
                item = {
                    **data,
                    'author': author_data,
                    'categories': categories,
                    'count': comments_count,
                }
                item_list.append(item)

            responseData = {
                "type": "posts",
                "items": item_list
            }

            return Response(responseData, status=200)

        except Exception as e:
            print(e)
            return Response("cannot read post", status=500)
            

    # Create new post
    elif request.method == 'POST':
        currentAuthor = Authors.objects.filter(uuid=pk).first()
        new_post = request.data
        new_postId = uuid.uuid4()
        id = f"{request.build_absolute_uri('/')[:-1]}/service/authors/{str(pk)}/posts/{str(new_postId)}"

        newPost = Posts.objects.create(
            title=new_post['title'],
            uuid=new_postId,
            id=id,
            source=new_post['source'],
            origin=new_post['origin'],
            description=new_post['description'],
            contentType=new_post['contentType'],
            content=new_post['content'],
            author=currentAuthor,
            categories=new_post['categories'],
            count=0,
            visibility=new_post['visibility'],
        )
        newPost.save()
        return Response(status=200)
    return Response(status=400)  # Return bad request if method is not GET or POST


get_post_example = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'title': openapi.Schema(type=openapi.TYPE_STRING, description='Title of the post'),
        'source': openapi.Schema(type=openapi.TYPE_STRING, description='Source of the post'),
        'description': openapi.Schema(type=openapi.TYPE_STRING, description='Description of the post'),
        'contentType': openapi.Schema(type=openapi.TYPE_STRING, description='Content type of the post'),
        'content': openapi.Schema(type=openapi.TYPE_STRING, description='Content of the post'),
        'visibility': openapi.Schema(type=openapi.TYPE_STRING, description='Visibility of the post'),
        'categories': openapi.Schema(type=openapi.TYPE_STRING, description='Categories of the post'),
    },
)

@swagger_auto_schema(method='put', operation_description="Update a specific post, non required.")
@swagger_auto_schema(method='delete', operation_description="Delete a specific post.")
@swagger_auto_schema(method='get', operation_description="Get a specific post.")
@api_view(['GET', 'PUT', 'DELETE'])
def get_post(request, pk, postsId):
    """
    This view is used to get a specific post, update a specific post, or delete a specific post
    """
    # Get a specific post
    if request.method == 'GET':
        post = Posts.objects.get(uuid=postsId)
        if not post:
            return Response(status=404)
        #get post image data and encode it
        img = post.contentImage.url if post.contentImage else ""
        if img:
            send_img = get_image(img)
        else:
            send_img = None
        #organize the data to be returned
        post_dict = {
            'title': post.title,
            'id': post.id,
            'uuid': post.uuid,
            'source': post.source,
            'description': post.description,
            'contentType': post.contentType,
            'content': post.content,
            'contentImage': send_img,
            'origin': post.origin,
            'published': post.published,
            'visibility': post.visibility,
            'categories': post.categories,
            'author': {
                'id': post.author.id,
                'uuid': post.author.uuid,
                'displayName': post.author.displayName,
                'github': post.author.github,
                'host': post.author.host,
                'url': post.author.url,
            },
            'count': post.count,
        }
        return Response(post_dict)

    # Update an existing post
    elif request.method == 'PUT':
        post = Posts.objects.get(author__uuid=pk, uuid=postsId)
        if not post:
            return Response(status=404)
        #update the post with the new data
        post.title = request.data.get('title', post.title)
        post.source = request.data.get('source', post.source)
        post.description = request.data.get('description', post.description)
        post.contentType = request.data.get('contentType', post.contentType)
        post.content = request.data.get('content', post.content)
        post.visibility = request.data.get('visibility', post.visibility)
        post.categories = request.data.get('categories', post.categories)
        uid = str(uuid.uuid4())
        #get the image data and encode it
        if 'contentImage' in request.data:
            contentImage_data = request.data.get('contentImage')
            if contentImage_data:
                format, imgstr = contentImage_data.split(';base64,')
                ext = format.split('/')[-1]
                decoded_image = ContentFile(base64.b64decode(imgstr), name=f'{uid}.{ext}')
                contentImage = decoded_image
        else:
            contentImage = post.contentImage
        post.contentImage = contentImage

        post.save()
        return Response(status=200)

    # Delete a post
    elif request.method == 'DELETE':
        post = Posts.objects.get(author__uuid=pk, uuid=postsId)
        if not post:
            return Response(status=404)

        post.delete()
        return Response(status=204)


@swagger_auto_schema(method='get', operation_description="Get all the comments of specific post.")
@api_view(['GET'])
def getComments(request, pk, postsId):
    """
    Get all the comments of specific post
    """
    if request.method == 'GET':
        item_list = []
        comments = Comments.objects.filter(post__uuid=postsId)
        #get the comments and organize the data to be returned
        try:
            comments = paginate(request, comments)
            #get the comments and organize the data to be returned
            for comment in comments:
                serializer = CommentSerializer(comment)
                data = serializer.data
                author = Authors.objects.get(username=data['author'])
                serializeAuthor = AuthorSerializer(author)
                author_data = serializeAuthor.data
                author_data['displayName'] = author_data.pop('displayName')
                comment_data = {**data, 'author': author_data}
                item_list.append(comment_data)

            responseData = {
                "type": 'comments',
                "items": item_list
            }

            return Response(responseData, status=200)
        except:
            for comment in comments:
                serializer = CommentSerializer(comment)
                data = serializer.data
                author = Authors.objects.get(username=data['author'])
                serializeAuthor = AuthorSerializer(author)
                author_data = serializeAuthor.data
                author_data['displayName'] = author_data.pop('displayName')
                comment_data = {**data, 'author': author_data}
                item_list.append(comment_data)

            responseData = {
                "type": 'comments',
                "items": item_list
            }

            return Response(responseData, status=200)

    elif request.method == 'POST':
        currentAuthor = Authors.objects.filter(uuid=pk).first()
        currentPost = Posts.objects.filter(uuid=postsId).first()
        new_comment = request.data
        new_COMM_UUId = uuid.uuid4()
        commentId = f"{request.build_absolute_uri('/')}service/authors/{str(pk)}/posts/{str(postsId)}/comments/{str(new_COMM_UUId)}"
        newComment = Comments.objects.create(uuid=new_COMM_UUId, id=commentId, post=currentPost, author=currentAuthor,
                                             comment=new_comment['comment'], contentType=new_comment['contentType']
                                             )
        newComment.save()
        return Response(status=200)

@swagger_auto_schema(method='get', operation_description="Get a specific comment.")
@api_view(['GET'])
def getOneComment(request, pk, postsId, commentId):
    '''
    get a specific comment
    '''
    if request.method == "GET":
        comment = Comments.objects.get(uuid=commentId)
        serializeComment = CommentSerializer(comment).data

        author = Authors.objects.get(username=serializeComment['author'])
        serializeAuthor = AuthorSerializer(author).data
        serializeAuthor['displayName'] = serializeAuthor.pop('displayName')

        serializeComment['author'] = serializeAuthor

        responseData = {
            "type": "comment",
            "items": [serializeComment]
        }

        return Response(responseData, status=200)

@swagger_auto_schema(method='get', operation_description="Get all the followers that follow current user.")
@api_view(['GET'])
def getFollowers(request, pk):
    """
    Get all the followers that following current user
    """
    if request.method == 'GET':
        oneFollowers = Followers.objects.filter(followedUser__uuid=pk)

        followerList = [AuthorSerializer(followers.follower).data for followers in oneFollowers]

        data = {
            "type": "followed user",
            "followersNum": len(followerList),
            "items": followerList,
        }

        return Response(data, status=200)

@swagger_auto_schema(method='get', operation_description="Get all the users followed by current user.")
@api_view(['GET'])
def getFollowing(request, pk):
    """
    Get all the users followed by current user
    """
    if request.method == 'GET':
        oneFollowers = Followers.objects.filter(follower__uuid=pk)

        followerList = [AuthorSerializer(followers.followedUser).data for followers in oneFollowers]

        data = {
            "type": "followed by user",
            "followedNum": len(followerList),
            "items": followerList,
        }

        return Response(data, status=200)

@swagger_auto_schema(method='put', operation_description="Add a new following relation, make sure the user send out follow request put after /followers/author_uuid.")
@swagger_auto_schema(method='delete', operation_description="Delete a following relation.")
@swagger_auto_schema(method='get', operation_description="Get information of a specific follower.")
@api_view(['DELETE', 'PUT', 'GET'])
def oneFollower(request, pk, foreignPk):
    """
    DELETE: delete the author<foreignPk> from author<pk>'s follower list<br>
    PUT: add a new author<foreignPk> to the author<pk>'s follower list<br>
    GET: if author<foreignPk> followed author<pk>, author details will be displayed
    """
    #get the current user and the foreign user
    try:
        current_user = Authors.objects.get(uuid=pk)
        foreign_user = Authors.objects.get(uuid=foreignPk)
    except Authors.DoesNotExist:
        return Response({"message": "User not found"}, status=404)

    if request.method == 'DELETE':
        #delete the follower relationship
        try:
            Followers.objects.get(follower=foreign_user, followedUser=current_user).delete()
            return Response({"message": "Unfollowed successfully"}, status=200)
        except Followers.DoesNotExist:
            return Response({"message": "No such follower relationship"}, status=404)

    elif request.method == 'PUT':
        connect_group1 = "https://p2psd.herokuapp.com" #change when ever need
        connect_group2 = "https://sd16-api.herokuapp.com" #change when ever need
        #check if the user is already followed
        if Followers.objects.filter(follower=foreign_user, followedUser=current_user):
            return Response({"message": "Already followed"}, status=400)
        else:
            #check if the user is trying to self follow
            if current_user == foreign_user:
                return Response({"message": "You cannot follow yourself"}, status=400)
            new_follow = Followers.objects.create(followedId=pk ,follower=foreign_user, followedUser=current_user)
            new_follow.save()
            #check if the user is trying to follow a romote user
            if foreign_user.uuid == foreign_user.username:
                all_node = Node.objects.all()
                uid = foreign_user.url.split('/')[-1]
                host = foreign_user.host
                #check which node the user is in
                for node in all_node:
                    temp_node = str(node.host).replace("/service","")
                    if str(host) == temp_node:
                        #organize the data to send and send the follow request to the remote user inbox
                        try:
                            inbox_url = f"{str(node.host)}/authors/{str(uid)}/inbox/"
                            send_actor = AuthorSerializer(foreign_user).data
                            send_object = AuthorSerializer(current_user).data
                            object = {
                                "approved": True,
                                "type": "follow",
                                "summary": f"{current_user.displayName} approved {foreign_user.displayName}'s follow request",
                                "actor": send_actor,
                                "object": send_object
                            }
                            #send the follow request to the remote user inbox
                            response = requests.post(inbox_url, data=object, auth=HTTPBasicAuth(str(node.username), str(node.password)))
                            print('this is response:',response.status_code, response.reason, response.text)
                            break
                        except Exception as e:
                            print('this is error:',e)
                            return Response({"message": "send approved follow request back fail"}, status=404)

            return Response({"message": "Followed successfully"}, status=200)

    elif request.method == 'GET':
        #check if the user is followed by the current user
        if Followers.objects.filter(follower=foreign_user, followedUser=current_user):
            data = {
                "isFollowed": True,
                "author": AuthorSerializer(current_user).data,
                "followed by": AuthorSerializer(foreign_user).data
            }
            return Response(data, status=200)
        else:
            return Response({"isFollowed": False}, status=200)


@swagger_auto_schema(method='post', operation_description="Create a follow request to current author.")
@api_view(['POST'])
def followRequest(request, pk, foreignPk):
    '''
    post a follow request to current author, foreignPk is the author who want to follow current author
    '''
    try:
        current_user = Authors.objects.get(uuid=pk)
        foreign_user = Authors.objects.get(uuid=foreignPk)
    except Authors.DoesNotExist:
        return Response({"message": "User not found"}, status=404)
    #check if the user is trying to self follow
    if current_user == foreign_user:
        return Response({"message": "You cannot follow yourself"}, status=404)
        
    author_name = foreign_user.displayName
    object_name = current_user.displayName
    belongTo = current_user.uuid
    summary = author_name + " wants to follow " + object_name
    
    if request.method == 'POST':
        #check if the user is already followed
        if not Followers.objects.filter(follower=foreign_user, followedUser=current_user):
            #create a follow request
            makeRequest = FollowRequests.objects.create(actor=foreign_user, object=current_user, belongTo=belongTo, summary=summary)
            makeRequest.save()

            send_author_inbox = Inbox.objects.get(author=current_user)
            send_author_inbox.followRequests.add(makeRequest)

            responseData = {
                "type": "creat followRequest" 
            }
            return Response(responseData, status=201)
        else:
            return Response({"message": "You are already following this user"}, status=404)
    else:
        responseData = {
            "type": "creat comment",
            "items": '[]'
        }
        return Response(responseData, status=200)


@swagger_auto_schema(method='get', operation_description="Get all the likes for a specific post.")
@api_view(['GET'])
def get_post_likes(request, pk, postsId):
    """
    Get all the likes for a specific post.
    """
    if request.method == "GET":
        #get the post and all the likes for the post
        try:
            post = Posts.objects.get(uuid=postsId)
            likes = Likes.objects.filter(object=post.id)
        except Posts.DoesNotExist:
            return Response({"detail":"Post not found"},status=404)

        items_list = []
        #get the author of the like and the like itself
        for like in likes:
            author = Authors.objects.get(uuid=like.author.uuid)
            author_dict = AuthorSerializer(author).data
            like_dict = LikedSerializer(like).data
            like_dict["author"] = author_dict
            items_list.append(like_dict)

        response_data = {
            "type": "likes",
            "total_likes": len(items_list),
            "items": items_list,
            
        }

        return Response(response_data, status=200)

@swagger_auto_schema(method='get', operation_description="Get all the posts liked by specific author.")
@api_view(['GET'])
def get_liked(request, pk):
    """
    Get a list of posts liked by an author
    """
    if request.method == "GET":
        #get the author and all the likes made by the author
        author = Authors.objects.get(uuid=pk)
        likes = Likes.objects.filter(author=author)
        
        items_list = []
        #get the post of the like and the like itself
        for like in likes:
            try:
                post = Posts.objects.get(id=like.object)
                
                post_dict = PostsSerializer(post).data
                
                items_list.append(post_dict)
            except Exception as e:
                print(e)
                continue
        response_data = {
            "type": "liked",
            "total_liked": len(items_list),
            "items": items_list,
        }

        return Response(response_data, status=200)

@swagger_auto_schema(method='get', operation_description="Get all comments liked by specific author.")
@api_view(['GET'])
def get_liked_comments(request, pk):
    """
    Get a list of comments liked by an author
    """
    if request.method == "GET":
        #get the author and all the likes made by the author
        author = Authors.objects.get(uuid=pk)
        likes = Likes.objects.filter(author=author)
        
        items_list = []
        for like in likes:
            #get the comment of the like and the like itself
            try:
                comment = Comments.objects.get(id=like.object)
                
                comment_dict = CommentSerializer(comment).data
                
                items_list.append(comment_dict)
            except Exception as e:
                print(e)
                continue
        response_data = {
            "type": "liked",
            "total_liked": len(items_list),
            "items": items_list,
        }

        return Response(response_data, status=200)

@swagger_auto_schema(method='get', operation_description="Get all the likes for a specific comment.")
@api_view(['GET'])
def get_comment_likes(request, pk, commentId):
    """
    Get all the likes for a specific comment.
    """
    if request.method == "GET":
        #get the comment and all the likes for the comment
        try:
            comment = Comments.objects.get(uuid=commentId)
            likes = Likes.objects.filter(object=comment.id)
        except Comments.DoesNotExist:
            return Response({"detail": "Comment not found."}, status=404)

        likes_list = []
        #get the author of the like and the like itself
        for like in likes:
            author = Authors.objects.get(uuid=like.author.uuid)
            author_dict = AuthorSerializer(author).data
            author_dict.pop("username")
            author_dict.pop("password")
            like_dict = LikedSerializer(like).data
            like_dict["author"] = author_dict
            likes_list.append(like_dict)

        response_data = {
            "type": "likes",
            "total_likes": len(likes_list),
            "items": likes_list,
        }

        return Response(response_data, status=200)

author_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'type': openapi.Schema(type=openapi.TYPE_STRING, description='Type of the object, author.'),
        'id': openapi.Schema(type=openapi.TYPE_STRING, description='author.id', minLength=1),
        'url': openapi.Schema(type=openapi.TYPE_STRING, description='author.url', minLength=1),
        'host': openapi.Schema(type=openapi.TYPE_STRING, description='author.host', minLength=1),
        'displayName': openapi.Schema(type=openapi.TYPE_STRING, description='author.displayname', maxLength=100, minLength=1),
        'github': openapi.Schema(type=openapi.TYPE_STRING, description='author.github'),
        'profileImage': openapi.Schema(type=openapi.TYPE_STRING, description='author.profileimage', x_nullable=True)
    },
    required=['id', 'url', 'host', 'displayName', 'github', 'profileImage'],
)

post_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'title': openapi.Schema(type=openapi.TYPE_STRING, description='Title of the post.', maxLength=100, minLength=1),
        'description': openapi.Schema(type=openapi.TYPE_STRING, description='Description of the post.', maxLength=1000, minLength=1),
        'contentImage': openapi.Schema(type=openapi.TYPE_STRING, description='Content image of the post.', x_nullable=True),
        'visibility': openapi.Schema(type=openapi.TYPE_STRING, description='Visibility of the post, public/private/unlisted.', maxLength=100, minLength=1),
        'contentType': openapi.Schema(type=openapi.TYPE_STRING, description='Content type of the post, text/markdown.', maxLength=100, minLength=1),
        'id': openapi.Schema(type=openapi.TYPE_STRING, description='Post id.', minLength=1),
        'origin': openapi.Schema(type=openapi.TYPE_STRING, description='Origin link of the post.', minLength=1),
        'author': author_schema,
        'categories': openapi.Schema(type=openapi.TYPE_STRING, description='Categories of the post.'),
        'count': openapi.Schema(type=openapi.TYPE_STRING, description='Number comments of the post.')

    },
    required=['title', 'description', 'contentImage', 'visibility', 'contentType', 'id', 'origin', 'author', 'categories', 'count'],
)

followRequest_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'approved': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Whether the follow request is approved or not, optional,used for create follow request we send and accept by your user.'),
        'type': openapi.Schema(type=openapi.TYPE_STRING, description='Type of the object, follow.'),
        'summary': openapi.Schema(type=openapi.TYPE_STRING, description='Summary of the follow.', x_nullable=True),
        'actor': author_schema,
        'object': author_schema

    },
    required=['type', 'summary', 'author'],
)

sharePost_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'type': openapi.Schema(type=openapi.TYPE_STRING, description='Type of the object, post.'),
        'sender': author_schema,
        'post': post_schema

    },
    required=['type', 'summary', 'author'],
)

new_likes_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'type': openapi.Schema(type=openapi.TYPE_STRING, description='Type of the object, like.'),
        'p_or_c': openapi.Schema(type=openapi.TYPE_STRING, description='Whether the like is for a post or a comment.'),
        'postId': openapi.Schema(type=openapi.TYPE_STRING, description='Post id, if comment no need this.'),
        'commentId': openapi.Schema(type=openapi.TYPE_STRING, description='Comment id, if post no need this.'),
        'author': author_schema,
    },
    required=['type', 'p_or_c', 'author'],
)

new_comment_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'type': openapi.Schema(type=openapi.TYPE_STRING, description='Type of the object, comment.'),
        'postId': openapi.Schema(type=openapi.TYPE_STRING, description='Post id.'),
        'comment': openapi.Schema(type=openapi.TYPE_STRING, description='Comment content.'),
        'contentType': openapi.Schema(type=openapi.TYPE_STRING, description='Content type of the comment, text/markdown,text/plain, image.'),
        'author': author_schema,

    },
    required=['type', 'postId', 'comment', 'author', 'contentType'],
)

inbox_example = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'sharePost': sharePost_schema,
        'followRequest': followRequest_schema,
        'newLikes': new_likes_schema,
        'newComment': new_comment_schema,
    },
    required=['type'],
)

@swagger_auto_schema(method='post', operation_description="Create posts or comments or follow requests or likes to specific author's inbox.", request_body=inbox_example)
@swagger_auto_schema(method='delete', operation_description="Clear inbox for specific author.")
@swagger_auto_schema(method='get', operation_description="Get all the posts, comments, follow requests and likes in specific author's inbox.")
@api_view(['GET', 'DELETE', 'POST'])

def inbox(request, pk):
    '''
    GET: get all the posts, comments, follow requests and likes in specific author's inbox.
    POST: create share posts or comments to specific post or follow requests or likes post or comment to specific author's inbox.
    DELETE: clear inbox for specific author.
    '''
    if request.method == 'GET':
        
        try:
            # get the author's inbox
            author = Authors.objects.get(uuid=pk)
            author_inbox = Inbox.objects.get(author=author)
            # get all the posts in the inbox
            posts_list = [ShareSerializer(post).data for post in author_inbox.posts.all()]
            #show the author's profile image and post's image and all the information, not just the id
            for i in posts_list:
                user = Authors.objects.get(username=i['author'])
                i['author'] = AuthorSerializer(user).data
                i['author']['profileImage'] = get_image(i['author']['profileImage']) if i['author']['profileImage'] else ""
                temp_post = Posts.objects.get(id=i['post'])
                i['post'] = PostsSerializer(temp_post).data
                temp_post_author = Authors.objects.get(username=i['post']['author'])
                i['post']['author'] = AuthorSerializer(temp_post_author).data
                i['post']['author']['profileImage'] = get_image(i['post']['author']['profileImage']) if i['post']['author']['profileImage'] else ""
                i['post']['contentImage'] = get_image(i['post']['contentImage']) if i['post']['contentImage'] else ""
            # get all the comments in the inbox
            comments_list = [CommentSerializer(comment).data for comment in author_inbox.comments.all()]
            #show the author's profile image and all the information, not just the id
            for i in comments_list:
                user = Authors.objects.get(username=i['author'])
                i['author'] = AuthorSerializer(user).data
            # get all the follow requests in the inbox
            follow_requests_list = [FollowRequestSerializer(request).data for request in author_inbox.followRequests.all()]
            #show the author informations, not just the id
            for i in follow_requests_list:
                user_a = Authors.objects.get(username=i['actor'])
                user_b = Authors.objects.get(username=i['object'])
                i['actor'] = AuthorSerializer(user_a).data
                i['object'] = AuthorSerializer(user_b).data
            # get all the likes in the inbox
            likes_list = [LikedSerializer(like).data for like in author_inbox.likes.all()]
            #show the author informations, not just the id
            for i in likes_list:
                user = Authors.objects.get(username=i['author'])
                i['author'] = AuthorSerializer(user).data
            # put all the posts, comments, follow requests and likes in the inbox into a list
            data_list = []
            data_list.append(posts_list)
            data_list.append(comments_list)
            data_list.append(follow_requests_list)
            data_list.append(likes_list)

            response_data = {
                "type": "inbox",
                "author": author.uuid,
                "items": data_list,
            }

            return Response(response_data, status=200)
        except :
            return Response(status=404)
        


    elif request.method == 'POST':
        # get the author's inbox
        try:
            author = Authors.objects.get(uuid=pk)
            inbox = Inbox.objects.get(author=author)
        except (Authors.DoesNotExist, Inbox.DoesNotExist):
            return Response({"message": "No such user"}, status=404)

        post_type = request.data.get('type')
        # if the post type is share post
        if post_type == 'post':
            post_entity = request.data.get('post')
            sender = request.data.get('sender')
            # if the sender is not the author stored in the local database
            if Authors.objects.filter(url=sender.get('url')):
                sender_author = Authors.objects.get(url=sender.get('url'))############
            else:
                # create a new author with the sender's information for the local database to store
                uid = str(sender.get('url')).split('/')[-1]
                temp = Authors.objects.create(username=uid, password=uid, uuid=uid, displayName=sender.get("displayName"), host=sender.get('host'), url=sender.get('url'), github=sender.get('github'), profileImage=sender.get("profileImage"), id=f"{request.build_absolute_uri('/')[:-1]}/service/authors/{uid}")
                temp.save()
                sender_author = Authors.objects.get(uuid=uid)
            # if the post is already in the local database get the post
            if Posts.objects.filter(source=post_entity.get('id')):
                selectedPost = Posts.objects.get(source=post_entity.get('id'))##############
            else:
                # if the post is not in the local database, create a new post with the post's information for the local database to store
                temp_author = post_entity.get('author')
                # if the post's author is not in the local database
                if Authors.objects.filter(url=temp_author.get('url')):
                    post_author = Authors.objects.get(url=temp_author.get('url'))############
                else:
                    # create a new author with the post's author's information for the local database to store
                    uid = str(temp_author.get('url')).split('/')[-1]
                    temp = Authors.objects.create(username=uid, password=uid, uuid=uid, displayName=temp_author.get("displayName"), host=temp_author.get('host'), url=temp_author.get('url'), github=temp_author.get('github'), profileImage=temp_author.get("profileImage"), id=f"{request.build_absolute_uri('/')[:-1]}/service/authors/{uid}")
                    temp.save()
                    post_author = Authors.objects.get(uuid=uid)
                
                uid = str(post_entity.get('id')).split('/')[-1]
                temp1 = Posts.objects.create(
                    title=post_entity.get('title'),
                    description=post_entity.get('description'),
                    contentType=post_entity.get('contentType'),
                    content=post_entity.get('content'),
                    visibility=post_entity.get('visibility'),
                    uuid = uid,
                    id = f"{request.build_absolute_uri('/')[:-1]}/service/authors/{str(post_author.uuid)}/posts/{uid}",
                    source=post_entity.get('id'),
                    origin=post_entity.get('origin'),
                    author=post_author,
                    categories=post_entity.get('categories'),
                    count=post_entity.get('count'),
                )

                temp1.save()
                selectedPost = Posts.objects.get(uuid = uid)
                
            newShare = Shares.objects.create(post=selectedPost, author=sender_author)
            newShare.save()

            inbox.posts.add(newShare)
            inbox.save()
            return Response(status=201)
        # if the post type is follow request
        elif post_type == 'follow':
            #check if the follow request is accepted by remote author
            if request.data.get('approved') and request.data.get('approved')=="true":
                #get the information and create this follow relationship in the local database
                try:
                    actor = request.data.get('object')
                    if Authors.objects.filter(url=actor.get('url')):
                        foreign_user = Authors.objects.get(url=actor.get('url'))
                    else:
                        uid = str(actor.get('url')).split('/')[-1]
                        temp = Authors.objects.create(username=uid, password=uid, uuid=uid, displayName=actor.get("displayName"), host=actor.get('host'), url=actor.get('url'), github=actor.get('github'), profileImage=actor.get("profileImage"), id=f"{request.build_absolute_uri('/')[:-1]}/service/authors/{uid}")
                        temp.save()
                        foreign_user = Authors.objects.get(uuid=uid)

                    
                    current_user = Authors.objects.get(uuid=pk)
                    
                except Authors.DoesNotExist:
                    return Response({"message": "User not found"}, status=404)

                if current_user == foreign_user:
                    return Response({"message": "You cannot follow yourself"}, status=404)
                    
                author_name = current_user.displayName
                object_name = foreign_user.displayName
                belongTo = foreign_user.uuid
                summary = author_name + " wants to follow " + object_name
                print(summary)
                #check if the follow relationship already exists
                if not Followers.objects.filter(follower=current_user, followedUser=foreign_user):
                    #create a new follow relationship in the local database
                    try:
                        makeRequest = FollowRequests.objects.create()
                        
                        makeRequest.summary = summary
                        makeRequest.actor = current_user
                        makeRequest.object = foreign_user
                        makeRequest.save()
                    except Exception as e:
                        print('this is error:',e)
                        return Response({"message": "Follow request failed"}, status=404)
                    #create a new follow relationship in the local database using the service url of create follow relationship
                    try:

                        follow_url = f"{request.build_absolute_uri('/')[:-1]}/service/authors/{str(pk)}/followers/{str(foreign_user.uuid)}/"

                        response = requests.put(follow_url, data={"approved": True}, auth=HTTPBasicAuth(str(current_user.username), str(current_user.password)))

                    except Exception as e:
                        print('this is error:',e)
                        return Response({"message": "Create follow fail, either url problem or response problem"}, status=404)
                    
                    if response.status_code == 200 or response.status_code == 201:
                        return Response({"message": "Successfully create the relation on our side too"}, status=200)
                    else:

                        return Response({"message":"response give error"}, status=404)


                else:
                    return Response({"message": "You are already following this user"}, status=404)
            #if the follow request is send by remote author or local author
            else:    
                #get the information and create this follow request in the local database
                try:
                    actor = request.data.get('actor')
                    
                    if Authors.objects.filter(url=actor.get('url')):
                        current_user = Authors.objects.get(url=actor.get('url'))
                    else:
                        uid = str(actor.get('url')).split('/')[-1]
                        temp = Authors.objects.create(username=uid, password=uid, uuid=uid, displayName=actor.get("displayName"), host=actor.get('host'), url=actor.get('url'), github=actor.get('github'), profileImage=actor.get("profileImage"), id=f"{request.build_absolute_uri('/')[:-1]}/service/authors/{uid}")
                        temp.save()
                        current_user = Authors.objects.get(uuid=uid)

                    
                    foreign_user = Authors.objects.get(uuid=pk)
                    
                except Authors.DoesNotExist:
                    return Response({"message": "User not found"}, status=404)

                if current_user == foreign_user:
                    return Response({"message": "You cannot follow yourself"}, status=404)
                    
                author_name = current_user.displayName
                object_name = foreign_user.displayName
                belongTo = foreign_user.uuid
                summary = author_name + " wants to follow " + object_name
                print(summary)
                #check if the follow relationship already exists
                if not Followers.objects.filter(follower=current_user, followedUser=foreign_user):
                    #create a new follow request in the local database
                    try:
                        makeRequest = FollowRequests.objects.create()
                        
                        makeRequest.summary = summary
                        makeRequest.actor = current_user
                        makeRequest.object = foreign_user
                        makeRequest.save()
                    except Exception as e:
                        print('this is error:',e)
                        return Response({"message": "Follow request failed"}, status=404)
                    #store the follow request to author inbox
                    inbox.followRequests.add(makeRequest)
                    inbox.save()
                    return Response(status=201)
                else:
                    return Response({"message": "You are already following this user"}, status=404)
        # if the post type is like
        elif post_type == 'like': 
            #get the information and create this like relationship in the local database
            try:
                #get like post or comment
                p_or_c = request.data.get('p_or_c')#get post or comment
                user = request.data.get('author')
                #get the author
                if Authors.objects.filter(url=user.get('url')):
                    currentAuthor = Authors.objects.get(url=user.get('url'))
                #if the author is not in the local database, create a new author in the local database to store the like relationship
                else:
                    uid = str(user.get('url')).split('/')[-1]
                    temp = Authors.objects.create(username=uid, password=uid, uuid=uid, displayName=user.get("displayName"), host=user.get('host'), url=user.get('url'), github=user.get('github'), profileImage=user.get("profileImage"), id=f"{request.build_absolute_uri('/')[:-1]}/service/authors/{uid}")
                    temp.save()
                    currentAuthor = Authors.objects.get(uuid=uid)
                author_name = currentAuthor.displayName
                
                if p_or_c == "post":
                    postId = request.data.get('postId')
                    post = Posts.objects.get(uuid=postId).id
                elif p_or_c == "comment":
                    commentId = request.data.get('commentId')
                    post = Comments.objects.get(uuid=commentId).id
                
                summary = author_name + " liked your "+p_or_c
            except Exception as e:
                print('this is error:',e)
                return Response({"message": "Post not found"}, status=404)

            #check if the like already exists
            if not Likes.objects.filter(author=currentAuthor, object=post):
                like = Likes.objects.create(author=currentAuthor, summary=summary, object=post)
                like.save()
                #check if the liked object already exists
                if not Liked.objects.filter(object=post):
                    receiver_liked = Liked.objects.create(object=post)
                liked = Liked.objects.get(object=post)
                liked.items.add(like)
                
                if not inbox.likes.filter(id=like.id):
                    inbox.likes.add(like)
                    inbox.save()
                    return Response(status=201)
                else:
                    return Response({"message": "You have already liked this post"}, status=404)
            else:
                return Response({"message": "You have already liked this post"}, status=404)

        # if the post type is comment
        elif post_type == 'comment':
            #get the information and create this comment in the local database
            comment = request.data.get('comment')
            postId = request.data.get('postId')
            user = request.data.get('author')
            if Authors.objects.filter(url=user.get('url')):
                currentAuthor = Authors.objects.get(url=user.get('url'))
            else:
                uid = str(actor.get('url')).split('/')[-1]
                temp = Authors.objects.create(username=uid, password=uid, uuid=uid, displayName=actor.get("displayName"), host=actor.get('host'), url=actor.get('url'), github=actor.get('github'), profileImage=actor.get("profileImage"), id=f"{request.build_absolute_uri('/')[:-1]}/service/authors/{uid}")
                temp.save()
                currentAuthor = Authors.objects.get(uuid=uid)

            
            content_type = request.data.get('content_type', 'text/plain')
            uid = str(uuid.uuid4())
            # create a new comment in the local database
            newComment = Comments()
            newComment.comment = comment
            newComment.contentType = content_type
            newComment.uuid = uid
            newComment.id = f"{request.build_absolute_uri('/')[:-1]}/service/authors/{str(currentAuthor.uuid)}/posts/{str(postId)}/comments/{uid}"
            newComment.author = currentAuthor
            currentPost = Posts.objects.get(uuid=postId)
            newComment.post = currentPost
            newComment.save()

            # Increment the post count and save the post
            currentPost.count = str(int(currentPost.count) + 1)
            currentPost.save()

            inbox.comments.add(newComment)
            inbox.save()
            return Response(status=201)

        else:
            return Response(status=400)
        
        inbox.save()
        return Response(status=201)

    # if the request is a DELETE request
    elif request.method == 'DELETE':
        #get the author inbox
        try:
            author = Authors.objects.get(uuid=pk)
            inbox = Inbox.objects.get(author=author)
        except (Authors.DoesNotExist, Inbox.DoesNotExist):
            return Response(status=404)
        #remove all the items in the inbox
        inbox.posts.clear()
        inbox.comments.clear()
        inbox.followRequests.clear()
        inbox.likes.clear()

        return Response(status=204)

    else:
        return Response(status=405)
    

