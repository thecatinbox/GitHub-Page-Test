import React, {useState, useEffect} from 'react';
import Post from '../../Components/Post/Post'; 
import AddPost from '../../Components/AddPost/AddPost'; 
import TopBar from "../../Components/TopBar/TopBar";
import './Home.css';

const postData = [
  {
    id: 1, 
    author: "Username1", 
    title: "Title1", 
    date: "2023-02-28", 
    content: "This is my first post. Lorem ipsum is placeholder text commonly used in the graphic, print, and publishing industries for previewing layouts and visual mockups."
  },
  {
    id: 2, 
    author: "Username2", 
    title: "Title2", 
    date: "2023-02-28", 
    content: "This is my second post. Lorem ipsum is placeholder text commonly used in the graphic, print, and publishing industries for previewing layouts and visual mockups."
  },
  {
    id: 3, 
    author: "Username3", 
    title: "Title3", 
    date: "2023-02-28", 
    content: "This is my third post. Lorem ipsum is placeholder text commonly used in the graphic, print, and publishing industries for previewing layouts and visual mockups."
  },
];


function Home() {

  const ENDPOINT = 'http://127.0.0.1:8000/server/authors/7dce957d-4ba2-4021-a76a-3ed8c4a06c97/posts/'

  const [postList, setPostList] = useState([]);

  useEffect(() => {
    fetch(ENDPOINT, {
      headers: { "Accept": "application/json" },
      method: "GET"
    }).then(response => response.json()).then(postData => {
      setPostList(postData.items);
      console.log(postData)
    });
  })

  return (
    <>
      <TopBar id="home"/>
      <div className="home">
        <AddPost/>
        {postList.map(function(post){
            return <Post post={post} key={post.id}/>;
        })}
        
      </div>
    </>

  );
}

export default Home;
