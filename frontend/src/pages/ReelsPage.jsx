import { useEffect, useMemo, useState } from "react";
import { api, apiGet, getToken, fileUrl } from "../api";
import { useNavigate } from "react-router-dom";
import VerifiedBadge from "../components/VerifiedBadge";

function Toast({ toast, onClose }) {
  if (!toast) return null;
  return (
    <div className="fixed top-4 left-0 right-0 z-50 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="bg-black text-white rounded-xl px-4 py-3 flex items-start gap-3 shadow-lg">
          <div className="text-sm leading-relaxed flex-1">{toast}</div>
          <button
            onClick={onClose}
            className="text-white/80 hover:text-white text-sm"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}

function EditModal({ open, initialValue, onClose, onSave }) {
  const [caption, setCaption] = useState(initialValue || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) setCaption(initialValue || "");
  }, [open, initialValue]);

  if (!open) return null;

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(caption);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4">
      <div className="w-full max-w-xl bg-white rounded-2xl border overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center justify-between">
          <div className="font-semibold">Edit description</div>
          <button onClick={onClose} className="text-sm opacity-70">
            Close
          </button>
        </div>

        <div className="p-4">
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            rows={6}
            className="w-full border rounded-xl p-3 text-sm outline-none focus:ring-2 focus:ring-black/10"
            placeholder="Update your caption (If product post, mention Ad / Sponsored / Paid partnership)"
          />
          <div className="mt-3 flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg border text-sm"
              disabled={saving}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 rounded-lg bg-black text-white text-sm"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReelsPage() {
  const nav = useNavigate();
  const token = getToken();

  const [feed, setFeed] = useState([]);
  const [me, setMe] = useState(null);

  const [toast, setToast] = useState(null);

  const [editOpen, setEditOpen] = useState(false);
  const [editPost, setEditPost] = useState(null);

  function showToast(msg) {
    if (!msg) return;
    setToast(msg);
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(() => setToast(null), 6000);
  }

  async function refreshAll() {
    const u = await apiGet("/api/auth/me", token);
    setMe(u);

    const all = await apiGet("/api/feed?limit=50&offset=0", token);

    // Optional: my posts first
    const sorted = [...all].sort((a, b) => {
      const am = a.user_id === u.user_id ? 0 : 1;
      const bm = b.user_id === u.user_id ? 0 : 1;
      if (am !== bm) return am - bm;
      return 0;
    });

    setFeed(sorted);
  }

  async function load() {
    try {
      await refreshAll();
    } catch (e) {
      nav("/auth");
    }
  }

  useEffect(() => {
    if (!token) nav("/auth");
    else load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const myUserId = me?.user_id || "";

  const myPostsMap = useMemo(() => {
    const map = new Map();
    for (const p of feed) map.set(p.id, p);
    return map;
  }, [feed]);

  async function onEditSave(newCaption) {
    if (!editPost?.id) return;

    try {
      const res = await api.editPostCaption(editPost.id, newCaption, token);

      // optimistic update (caption only)
      setFeed((prev) =>
        prev.map((p) => (p.id === editPost.id ? { ...p, caption: res.caption } : p))
      );

      if (res.warning) {
        showToast(res.warning);
      } else {
        showToast("Caption updated.");
      }

      // IMPORTANT: refresh after edit because badge may be revoked
      await refreshAll();
    } catch (e) {
      showToast(e.message || "Failed to update caption");
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 pb-24">
      <Toast toast={toast} onClose={() => setToast(null)} />

      <EditModal
        open={editOpen}
        initialValue={editPost?.caption || ""}
        onClose={() => setEditOpen(false)}
        onSave={onEditSave}
      />

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Reels</h1>
          {me?.username ? (
            <div className="text-xs opacity-70 mt-1">Logged in as @{me.username}</div>
          ) : null}
        </div>

        <button onClick={() => nav("/profile")} className="px-4 py-2 rounded-lg border">
          Profile
        </button>
      </div>

      {feed.length === 0 ? (
        <div className="text-gray-500">No reels yet. Create a post and refresh.</div>
      ) : (
        <div className="space-y-6">
          {feed.map((p) => {
            const isMine = myUserId && p.user_id === myUserId;

            return (
              <div key={p.id} className="bg-white border rounded-2xl overflow-hidden">
                {/* Username + badge + mine tag */}
                <div className="px-4 py-3 text-sm font-medium flex items-center gap-2 justify-between">
                  <div className="flex items-center gap-2">
                    <span>@{p.username}</span>
                    {p.is_verified ? <VerifiedBadge size={18} /> : null}
                    {isMine ? (
                      <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-black text-white">
                        My post
                      </span>
                    ) : null}
                  </div>

                  {/* Edit button only for my post */}
                  {isMine ? (
                    <button
                      onClick={() => {
                        setEditPost(myPostsMap.get(p.id) || p);
                        setEditOpen(true);
                      }}
                      className="text-xs px-3 py-1.5 rounded-full border hover:bg-gray-50"
                    >
                      Edit
                    </button>
                  ) : null}
                </div>

                {p.media_type === "video" ? (
                  <video
                    src={fileUrl(p.media_url)}
                    controls
                    className="w-full max-h-[520px] object-cover"
                  />
                ) : (
                  <img
                    src={fileUrl(p.media_url)}
                    alt={p.caption || "reel"}
                    className="w-full max-h-[520px] object-cover"
                  />
                )}

                {p.caption ? <div className="px-4 py-3 text-sm">{p.caption}</div> : null}
              </div>
            );
          })}
        </div>
      )}

      {/* bottom nav */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t">
        <div className="max-w-3xl mx-auto px-4 py-3 flex justify-around text-sm">
          <button onClick={() => nav("/reels")} className="font-semibold">
            Reels
          </button>
          <button onClick={() => nav("/profile")} className="text-gray-600">
            Profile
          </button>
        </div>
      </div>
    </div>
  );
}
