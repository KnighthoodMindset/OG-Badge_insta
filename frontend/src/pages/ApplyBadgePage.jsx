import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

function AgreementModal({ onClose }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white max-w-lg w-full p-6 rounded-xl shadow-lg">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="font-semibold">OG Badge Agreement</div>
          <button
            type="button"
            onClick={onClose}
            className="text-sm px-3 py-1 rounded-lg border"
          >
            ✕
          </button>
        </div>

        <div className="text-sm space-y-2 max-h-64 overflow-y-auto pr-1">
          <p>
            By applying for the Verified Badge, you agree to follow platform
            authenticity and advertisement disclosure rules.
          </p>
          <p>
            You must clearly mention “Ad” (or Sponsored / Paid Partnership) in
            product-related posts.
          </p>
          <p>
            Posting duplicate images from other accounts is not allowed for
            maintaining the badge.
          </p>
          <p>
            If you violate these rules after receiving the badge, it will be
            automatically removed.
          </p>
          <p>
            To regain the badge, you must correct the violation (edit/delete
            post) and reapply.
          </p>
          <p>
            The platform’s decision on approval or revocation is final based on
            automated system checks.
          </p>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="mt-4 w-full bg-black text-white py-2 rounded-lg"
        >
          Close
        </button>
      </div>
    </div>
  );
}

function normalizeList(arr) {
  return (Array.isArray(arr) ? arr : [])
    .map((x) => String(x ?? "").trim())
    .filter(Boolean);
}

export default function ApplyBadgePage() {
  const nav = useNavigate();
  const { token } = useAuth();

  const [me, setMe] = useState(null);
  const [myPostCount, setMyPostCount] = useState(0);

  const [form, setForm] = useState({
    brand_display_name: "",
    // NEW
    product_names: [""],
    // OLD (keep for backward compatibility, but we won’t rely on it)
    product_name: "",

    instagram_handle: "",
    legal_proof_type: "GST",

    // NEW
    gst_ids: [""],
    // OLD
    legal_proof_id: "",
  });

  const [status, setStatus] = useState(null);
  const [msg, setMsg] = useState("");
  const [agree, setAgree] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showAgreement, setShowAgreement] = useState(false);

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function setProductAt(i, v) {
    setForm((f) => {
      const next = [...(f.product_names || [])];
      next[i] = v;
      return { ...f, product_names: next };
    });
  }

  function addProduct() {
    setForm((f) => ({ ...f, product_names: [...(f.product_names || [""]), ""] }));
  }

  function removeProduct(i) {
    setForm((f) => {
      const next = [...(f.product_names || [])];
      next.splice(i, 1);
      return { ...f, product_names: next.length ? next : [""] };
    });
  }

  function setGstAt(i, v) {
    setForm((f) => {
      const next = [...(f.gst_ids || [])];
      next[i] = v;
      return { ...f, gst_ids: next };
    });
  }

  function addGst() {
    setForm((f) => ({ ...f, gst_ids: [...(f.gst_ids || [""]), ""] }));
  }

  function removeGst(i) {
    setForm((f) => {
      const next = [...(f.gst_ids || [])];
      next.splice(i, 1);
      return { ...f, gst_ids: next.length ? next : [""] };
    });
  }

  async function loadAll() {
    try {
      const u = await api.me(token);
      setMe(u);

      // lock brand name to username
      setForm((f) => ({ ...f, brand_display_name: u.username }));

      const posts = await api.myPosts(token);
      setMyPostCount(Array.isArray(posts) ? posts.length : 0);

      try {
        const s = await api.badgeStatus(token);
        setStatus(s);

        // If backend returns product_names/gst_ids, preload into form
        const serverProducts = normalizeList(s?.product_names);
        const serverGsts = normalizeList(s?.gst_ids);

        setForm((f) => ({
          ...f,
          product_names: serverProducts.length ? serverProducts : f.product_names,
          gst_ids: serverGsts.length ? serverGsts : f.gst_ids,
          legal_proof_type: s?.legal_proof_type || f.legal_proof_type,
          instagram_handle: s?.instagram_handle || f.instagram_handle,
        }));
      } catch {
        setStatus(null);
      }
    } catch {
      nav("/auth");
    }
  }

  useEffect(() => {
    if (token) loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const isApproved = status?.status === "APPROVED";

  const productsClean = useMemo(() => normalizeList(form.product_names), [form.product_names]);
  const gstsClean = useMemo(() => normalizeList(form.gst_ids), [form.gst_ids]);

  // Keep this aligned with your backend expectation (you currently check startsWith("GST") in UI)
  const allGstOk = useMemo(() => {
    if (form.legal_proof_type !== "GST") return true;
    if (gstsClean.length === 0) return false;
    return gstsClean.every((x) => x.toUpperCase().startsWith("GST"));
  }, [form.legal_proof_type, gstsClean]);

  const nonGstProofOk = useMemo(() => {
    if (form.legal_proof_type === "GST") return true;
    const id = String(form.legal_proof_id || "").trim();
    return id.length >= 6;
  }, [form.legal_proof_id, form.legal_proof_type]);

  const proofOk = allGstOk && nonGstProofOk;

  const canSubmit = useMemo(() => {
    return (
      !isApproved &&
      myPostCount > 0 &&
      productsClean.length > 0 &&
      productsClean.every((p) => p.length >= 2) &&
      proofOk &&
      agree &&
      !loading
    );
  }, [isApproved, myPostCount, productsClean, proofOk, agree, loading]);

  async function submit() {
    setMsg("");

    if (isApproved) {
      setMsg("You are already verified.");
      return;
    }

    if (!agree) {
      setMsg("You must agree to the badge rules before applying.");
      return;
    }

    if (myPostCount === 0) {
      setMsg("You must create at least 1 post before applying.");
      return;
    }

    if (productsClean.length === 0) {
      setMsg("At least 1 product name is required.");
      return;
    }

    if (!productsClean.every((p) => p.length >= 2)) {
      setMsg("Each product name must be at least 2 characters.");
      return;
    }

    if (!proofOk) {
      if (form.legal_proof_type === "GST") {
        setMsg("Each GST proof must start with GST (example: GST12345).");
      } else {
        setMsg("Proof ID must be at least 6 characters.");
      }
      return;
    }

    // Build payload for new backend
    const payload = {
      brand_display_name: form.brand_display_name,
      instagram_handle: form.instagram_handle || "",
      legal_proof_type: form.legal_proof_type,

      // NEW
      product_names: productsClean,

      // NEW (only used for GST)
      gst_ids: form.legal_proof_type === "GST" ? gstsClean : [],

      // OLD fallback fields (optional, but keeps compatibility)
      product_name: productsClean[0] || "",
      legal_proof_id:
        form.legal_proof_type === "GST"
          ? (gstsClean[0] || "")
          : (String(form.legal_proof_id || "").trim()),
    };

    try {
      setLoading(true);
      const res = await api.applyBadge(payload, token);
      setStatus(res);
      setMsg("Application submitted successfully.");
    } catch (e) {
      setMsg(e?.message || "Submission failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-4 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          className="px-3 py-2 rounded-xl border text-sm"
          onClick={() => nav(-1)}
        >
          Back
        </button>
        <div className="font-semibold">Apply for OG Badge</div>
      </div>

      {/* Status */}
      {status && (
        <div className="mt-4 border rounded-xl p-4">
          <div className="font-semibold">Current Status: {status.status}</div>
          <div className="text-sm mt-2">{status.reason}</div>
          {status.admin_note ? (
            <div className="text-sm mt-2 opacity-70">
              Admin: {status.admin_note}
            </div>
          ) : null}
        </div>
      )}

      {/* Rules */}
      <div className="mt-4 border rounded-xl p-4 text-sm">
        <div className="font-semibold mb-2">Important Rules</div>
        <div>
          • Product post must clearly mention: <b>Ad</b> (or Sponsored / Paid
          Partnership)
        </div>
        <div>
          • Duplicate images from other accounts are not allowed for maintaining
          badge.
        </div>
        <div>
          • If you violate rules after getting badge, it will be automatically
          removed.
        </div>
        <div>• Fix the issue (edit/delete) and reapply.</div>
      </div>

      {/* Form */}
      <div className="mt-4 border rounded-xl p-4">
        <div className="text-sm font-semibold mb-2">Application Form</div>

        <input
          className="w-full px-3 py-2 rounded-xl border bg-gray-100 opacity-70"
          value={form.brand_display_name}
          readOnly
        />

        <div className="text-xs mt-2 opacity-70">
          Brand is locked to your username: @{me?.username || ""}
        </div>

        <div className="text-xs mt-3 opacity-70">Your posts: {myPostCount}</div>
        {myPostCount === 0 ? (
          <div className="mt-2 text-sm text-red-600">
            You must create at least 1 post before applying.
          </div>
        ) : null}

        {/* PRODUCTS (MULTI) */}
        <div className="mt-4">
          <div className="text-xs opacity-70 mb-2">
            Products (each one must appear in at least one of your posts as: <span className="font-mono">product name: ...</span>)
          </div>

          {(form.product_names || [""]).map((val, i) => (
            <div key={i} className="flex gap-2 mt-2">
              <input
                className="flex-1 px-3 py-2 rounded-xl border"
                placeholder={`Product name ${i + 1} (required)`}
                value={val}
                onChange={(e) => setProductAt(i, e.target.value)}
                disabled={isApproved}
              />
              <button
                type="button"
                className="px-3 py-2 rounded-xl border text-sm"
                onClick={() => removeProduct(i)}
                disabled={isApproved || (form.product_names || []).length <= 1}
                title="Remove"
              >
                ✕
              </button>
            </div>
          ))}

          <button
            type="button"
            className="mt-3 px-3 py-2 rounded-xl border text-sm"
            onClick={addProduct}
            disabled={isApproved}
          >
            + Add product
          </button>

          {productsClean.length === 0 ? (
            <div className="text-xs mt-2 text-red-600">
              At least one product is required.
            </div>
          ) : null}
        </div>

        <input
          className="w-full mt-4 px-3 py-2 rounded-xl border"
          placeholder="Instagram handle (optional)"
          value={form.instagram_handle}
          onChange={(e) => set("instagram_handle", e.target.value)}
          disabled={isApproved}
        />

        {/* PROOF */}
        <div className="flex gap-2 mt-3">
          <select
            className="flex-1 px-3 py-2 rounded-xl border"
            value={form.legal_proof_type}
            onChange={(e) => set("legal_proof_type", e.target.value)}
            disabled={isApproved}
          >
            <option value="GST">GST</option>
            <option value="Trademark">Trademark</option>
            <option value="CompanyReg">CompanyReg</option>
          </select>

          {form.legal_proof_type === "GST" ? (
            <div className="flex-1" />
          ) : (
            <input
              className="flex-1 px-3 py-2 rounded-xl border"
              placeholder="Proof ID (min 6 chars)"
              value={form.legal_proof_id}
              onChange={(e) => set("legal_proof_id", e.target.value)}
              disabled={isApproved}
            />
          )}
        </div>

        {/* GSTs (MULTI) */}
        {form.legal_proof_type === "GST" ? (
          <div className="mt-4">
            <div className="text-xs opacity-70 mb-2">GSTINs (multiple allowed)</div>

            {(form.gst_ids || [""]).map((val, i) => (
              <div key={i} className="flex gap-2 mt-2">
                <input
                  className="flex-1 px-3 py-2 rounded-xl border"
                  placeholder={`GST ${i + 1} (e.g. GST12345)`}
                  value={val}
                  onChange={(e) => setGstAt(i, e.target.value)}
                  disabled={isApproved}
                />
                <button
                  type="button"
                  className="px-3 py-2 rounded-xl border text-sm"
                  onClick={() => removeGst(i)}
                  disabled={isApproved || (form.gst_ids || []).length <= 1}
                  title="Remove"
                >
                  ✕
                </button>
              </div>
            ))}

            <button
              type="button"
              className="mt-3 px-3 py-2 rounded-xl border text-sm"
              onClick={addGst}
              disabled={isApproved}
            >
              + Add GST
            </button>

            {!allGstOk && (form.gst_ids || []).some((x) => String(x || "").trim().length > 0) ? (
              <div className="text-xs mt-2 text-red-600">
                Each GST must start with GST.
              </div>
            ) : null}

            {gstsClean.length === 0 ? (
              <div className="text-xs mt-2 text-red-600">
                At least one GST is required.
              </div>
            ) : null}
          </div>
        ) : (
          !nonGstProofOk && String(form.legal_proof_id || "").trim().length > 0 ? (
            <div className="text-xs mt-2 text-red-600">
              Proof ID must be at least 6 characters.
            </div>
          ) : null
        )}

        {/* Agreement */}
        <div className="mt-4 border p-3 rounded-xl text-sm">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={agree}
              onChange={(e) => setAgree(e.target.checked)}
              disabled={isApproved}
            />
            <span>
              I agree to the badge rules{" "}
              <button
                type="button"
                onClick={() => setShowAgreement(true)}
                className="text-blue-600 underline text-xs"
                disabled={isApproved}
              >
                (View full agreement)
              </button>
            </span>
          </div>
        </div>

        <button
          className={`mt-4 w-full py-2 rounded-xl ${
            canSubmit
              ? "bg-black text-white"
              : "bg-gray-300 text-gray-600 cursor-not-allowed"
          }`}
          onClick={submit}
          disabled={!canSubmit}
        >
          {isApproved
            ? "Already Verified ✅"
            : loading
              ? "Submitting..."
              : "Submit Application"}
        </button>

        {msg ? <div className="text-sm mt-3 opacity-80">{msg}</div> : null}
      </div>

      {/* Modal */}
      {showAgreement ? (
        <AgreementModal onClose={() => setShowAgreement(false)} />
      ) : null}
    </div>
  );
}