import { useEffect, useRef, useState } from 'react';
import type { CollectionPhoto } from '../types';
import { uploadCollectionPhoto } from '../api/client';
import { resizeImage } from '../utils/imageResize';

interface CollectionUploadModalProps {
  onClose: () => void;
  onUploaded: (photo: CollectionPhoto) => void;
}

export default function CollectionUploadModal({ onClose, onUploaded }: CollectionUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [caption, setCaption] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef<string | null>(null);

  // Escape to close
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Clean up preview URL on unmount
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  function handleFileSelect(selected: File | null) {
    if (!selected) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(selected.type)) {
      setError('Only JPEG, PNG, and WebP images are allowed.');
      return;
    }
    if (selected.size > 2 * 1024 * 1024) {
      setError('Image must be smaller than 2MB.');
      return;
    }
    setError(null);
    setFile(selected);
    // Revoke previous preview URL
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
    }
    const url = URL.createObjectURL(selected);
    previewUrlRef.current = url;
    setPreview(url);
  }

  function handleRemoveFile() {
    setFile(null);
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setPreview(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const resized = await resizeImage(file, 1200, 1200, 0.85);
      const photo = await uploadCollectionPhoto(resized, caption.trim() || undefined);
      onUploaded(photo);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white border border-stone-200 rounded-2xl p-6 max-w-md w-full mx-4 relative shadow-lg">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-stone-400 hover:text-stone-700 transition-colors"
          aria-label="Close"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Title */}
        <h2 className="text-stone-900 font-semibold text-base mb-5">Add to Collection</h2>

        {/* File input area */}
        <div className="mb-4">
          {preview && file ? (
            <div className="relative rounded-xl overflow-hidden border border-stone-200">
              <img src={preview} alt="Preview" className="w-full h-48 object-cover" />
              <button
                onClick={handleRemoveFile}
                className="absolute top-2 right-2 bg-black/60 text-white rounded-full p-1 hover:bg-black/80 transition-colors"
                aria-label="Remove photo"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <div className="absolute bottom-0 left-0 right-0 bg-black/50 px-3 py-1.5">
                <p className="text-xs text-stone-200 truncate">{file.name}</p>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-full h-40 border-2 border-dashed border-stone-200 rounded-xl flex flex-col items-center justify-center gap-2 hover:border-stone-400 hover:bg-stone-50 transition-colors cursor-pointer"
            >
              <svg className="w-8 h-8 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              <span className="text-stone-500 text-sm">Click to select a photo</span>
              <span className="text-stone-400 text-xs">JPEG, PNG, WebP · max 2MB</span>
            </button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => handleFileSelect(e.target.files?.[0] ?? null)}
          />
        </div>

        {/* Caption */}
        <div className="mb-1">
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            maxLength={500}
            rows={2}
            placeholder="Add a description (optional)"
            className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:outline-none focus:border-stone-400 transition-colors resize-none"
          />
        </div>
        {caption.length > 0 && (
          <p className="text-xs text-stone-400 text-right mb-3">{caption.length}/500</p>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="w-full flex items-center justify-center gap-2 py-2.5 text-sm font-medium bg-stone-800 hover:bg-stone-700 text-white rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading && (
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          )}
          {uploading ? 'Uploading…' : 'Add to Collection'}
        </button>
      </div>
    </div>
  );
}
