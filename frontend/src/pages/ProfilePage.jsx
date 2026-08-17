import { useEffect, useState } from "react";
import {
  api,
  apiGet,
  apiPostForm,
  apiDelete,
  fileUrl,
  getToken,
} from "../api";
import { useNavigate } from "react-router-dom";
import VerifiedBadge from "../components/VerifiedBadge";

function Toast({ msg, onClose }) {
  if (!msg) return null;

  return (
    <div className="fixed top-4 left-0 right-0 z-50 px-4">
      <div className="max-w-3xl mx-auto bg-black text-white px-4 py-3 rounded-xl flex justify-between">
        <div className="text-sm">{msg}</div>
        <button onClick={onClose}>✕</button>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const nav = useNavigate();
  const token = getToken();

  const [me, setMe] = useState(null);
  const [posts, setPosts] = useState([]);
  const [badge, setBadge] = useState(null);

  const [file, setFile] = useState(null);
  const [caption, setCaption] = useState("");
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState("");

  const [editingId, setEditingId] = useState(null);
  const [editCaption, setEditCaption] = useState("");

  function showToast(t) {
    setToast(t);
    setTimeout(() => setToast(""), 5000);
  }

  async function load() {
    try {
      const u = await api.me(token);
      setMe(u);

      try {
        const b = await api.badgeStatus(token);
        setBadge(b);
      } catch {
        setBadge(null);
      }

      const my = await api.myPosts(token);
      setPosts(Array.isArray(my) ? my : []);
    } catch {
      nav("/auth");
    }
  }

  useEffect(() => {
    if (!token) nav("/auth");
    else load();
  }, []);

  async function onCreatePost(e) {
    e.preventDefault();
    if (!file) return showToast("Choose an image.");

    const form = new FormData();
    form.append("media", file);
    form.append("caption", caption);

    try {
      setLoading(true);
      const res = await apiPostForm("/api/posts", form, token);

      if (res.warning) showToast(res.warning);

      setFile(null);
      setCaption("");
      await load(); // refresh posts + badge
    } catch (e) {
      showToast(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function deletePost(postId) {
    if (!window.confirm("Delete this post?")) return;

    try {
      await apiDelete(`/api/posts/${postId}`, token);
      setPosts((prev) => prev.filter((p) => p.id !== postId));
      await load(); // refresh badge status
    } catch (e) {
      showToast(e.message);
    }
  }

  async function saveEdit(postId) {
    try {
      const res = await api.editPostCaption(postId, editCaption, token);

      if (res.warning) showToast(res.warning);
      else showToast("Updated.");

      setEditingId(null);
      await load();
    } catch (e) {
      showToast(e.message);
    }
  }

  const isApproved = badge?.status === "APPROVED";

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 pb-24">
      <Toast msg={toast} onClose={() => setToast("")} />

      {/* HEADER */}
      <div className="flex justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 font-medium">
            @{me?.username}
            {isApproved && <VerifiedBadge size={18} />}
          </div>
          <div className="text-sm text-gray-500">{me?.email}</div>
        </div>

        {/* RIGHT BUTTONS */}
        <div className="flex gap-2">

          <button
            onClick={() => nav("/settings")}
            className="border px-4 py-2 rounded"
          >
            Settings
          </button>

          <button
            onClick={() => nav("/reels")}
            className="border px-4 py-2 rounded"
          >
            Reels
          </button>
        </div>
      </div>

      {/* CREATE POST */}
      <form onSubmit={onCreatePost} className="border p-4 rounded-xl bg-white">
        <input type="file" onChange={(e) => setFile(e.target.files?.[0])} />

        <input
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          placeholder="Caption"
          className="border w-full mt-2 px-3 py-2 rounded"
        />

        <button className="mt-3 bg-black text-white w-full py-2 rounded">
          {loading ? "Posting..." : "Post"}
        </button>
      </form>

      {/* POSTS */}
      <div className="grid grid-cols-2 gap-4 mt-6">
        {posts.map((p) => (
          <div key={p.id} className="border rounded-xl bg-white">
            <div className="flex justify-between text-xs px-3 py-2 border-b">
              <span>Post</span>

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setEditingId(p.id);
                    setEditCaption(p.caption || "");
                  }}
                >
                  Edit
                </button>

                <button
                  className="text-red-600"
                  onClick={() => deletePost(p.id)}
                >
                  Delete
                </button>
              </div>
            </div>

            <img
              src={fileUrl(p.media_url)}
              className="w-full h-52 object-cover"
            />

            {editingId === p.id ? (
              <div className="p-3">
                <textarea
                  value={editCaption}
                  onChange={(e) => setEditCaption(e.target.value)}
                  className="border w-full px-2 py-2 rounded"
                />

                <button
                  onClick={() => saveEdit(p.id)}
                  className="mt-2 bg-black text-white px-3 py-1 rounded text-sm"
                >
                  Save
                </button>
              </div>
            ) : (
              p.caption && <div className="p-3 text-sm">{p.caption}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
