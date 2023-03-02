import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import TopBar from "./Components/TopBar/TopBar";
import Home from "./Pages/Home/Home";
import Inbox from "./Pages/Inbox/Inbox";
import Friends from "./Pages/Friends/Friends";
import Profile from "./Pages/Profile/Profile";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<TopBar id="home"/>}>
          <Route index element={<Home />} />
          <Route path="inbox" element={<Inbox />} />
          <Route path="friends" element={<Friends />} />
          <Route path="profile" element={<Profile />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);