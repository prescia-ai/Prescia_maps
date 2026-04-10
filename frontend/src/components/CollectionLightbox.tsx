import { useEffect, useRef, useState } from 'react';
import type { CollectionPhoto } from '../types';

interface CollectionLightboxProps {
  photos: CollectionPhoto[];
  initialIndex: number;
  isOwner: boolean;
  onClose: () => void;
  onEdit: (photoId: string, newCaption: string | null) => void;
  onDelete: (photoId: string) => void;
}

export default function CollectionLightbox({
  photos,
  initialIndex,
  isOwner,
  onClose,
  onEdit,
  onDelete,
}: CollectionLightboxProps) {
  const [index, setIndex] = useState(initialIndex);
  const [editMode, setEditMode] = useState(false);
  const [editCaption, setEditCaption] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const photo = photos[index];

  // Sync index when initialIndex changes (e.g. after deletion)
  useEffect(() => {
    setIndex(Math.min(initialIndex, photos.length - 1));
  }, [initialIndex, photos.length]);

  // Reset edit/delete state when photo changes
  useEffect(() => {
    setEditMode(false);
    setConfirmDelete(false);
    setEditCaption(photo?.caption ?? '');
  }, [index, photo]);

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        if (editMode) {
          setEditMode(false);
        } else if (confirmDelete) {
          setConfirmDelete(false);
        } else {
          onClose();
        }
      }
      if (!editMode) {
        if (e.key === 'ArrowLeft') setIndex((i) => Math.max(0, i - 1));
        if (e.key === 'ArrowRight') setIndex((i) => Math.min(photos.length - 1, i + 1));
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, editMode, confirmDelete, photos.length]);

  // Focus textarea when entering edit mode
  useEffect(() => {
    if (editMode && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [editMode]);

  if (!photo) return null;

  // Use higher-res URL for lightbox display
  const highResUrl = photo.url.replace('sz=w800-h800', 'sz=w1600-h1600');

  function handleSaveCaption() {
    onEdit(photo.id, editCaption.trim() || null);
    setEditMode(false);
  }

  function handleConfirmDelete() {
    onDelete(photo.id);
    setConfirmDelete(false);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/90"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors z-10"
        aria-label="Close"
      >
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Image counter */}
      {photos.length > 1 && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 text-slate-400 text-sm">
          {index + 1} / {photos.length}
        </div>
      )}

      {/* Left arrow */}
      {photos.length > 1 && index > 0 && (
        <button
          onClick={() => setIndex((i) => i - 1)}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors z-10"
          aria-label="Previous"
        >
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Right arrow */}
      {photos.length > 1 && index < photos.length - 1 && (
        <button
          onClick={() => setIndex((i) => i + 1)}
          className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors z-10"
          aria-label="Next"
        >
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      {/* Image */}
      <div className="flex flex-col items-center max-w-4xl w-full px-16 gap-4">
        <img
          src={highResUrl}
          alt={photo.caption || 'Collection photo'}
          className="max-h-[70vh] max-w-full object-contain rounded-lg"
        />

        {/* Caption + owner controls */}
        <div className="w-full max-w-2xl flex flex-col gap-2">
          {editMode ? (
            <div className="flex flex-col gap-2">
              <textarea
                ref={textareaRef}
                value={editCaption}
                onChange={(e) => setEditCaption(e.target.value)}
                maxLength={500}
                rows={3}
                placeholder="Add a description (optional)"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:outline-none focus:border-stone-400 transition-colors resize-none"
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-stone-400">{editCaption.length}/500</span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setEditMode(false)}
                    className="px-3 py-1.5 text-sm text-stone-400 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveCaption}
                    className="px-4 py-1.5 text-sm font-medium bg-stone-800 hover:bg-stone-700 text-white rounded-lg transition-colors"
                  >
                    Save
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {photo.caption ? (
                  <p className="text-stone-200 text-sm leading-relaxed">{photo.caption}</p>
                ) : isOwner ? (
                  <p className="text-stone-500 text-sm italic">No caption</p>
                ) : null}
              </div>

              {isOwner && (
                <div className="flex items-center gap-2 flex-shrink-0">
                  {confirmDelete ? (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-stone-400">Delete this photo?</span>
                      <button
                        onClick={handleConfirmDelete}
                        className="px-3 py-1 text-xs font-medium bg-red-700 hover:bg-red-600 text-white rounded-lg transition-colors"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => setConfirmDelete(false)}
                        className="px-3 py-1 text-xs text-stone-400 hover:text-white transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      {/* Edit caption button */}
                      <button
                        onClick={() => {
                          setEditCaption(photo.caption ?? '');
                          setEditMode(true);
                        }}
                        title="Edit caption"
                        className="text-slate-400 hover:text-white transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </button>
                      {/* Delete button */}
                      <button
                        onClick={() => setConfirmDelete(true)}
                        title="Delete photo"
                        className="text-slate-400 hover:text-red-400 transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
