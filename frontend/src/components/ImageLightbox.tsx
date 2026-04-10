import { useEffect, useState } from 'react';

interface ImageLightboxProps {
  images: Array<{ id: string; url: string; position: number }>;
  initialIndex: number;
  onClose: () => void;
}

function fullResUrl(url: string): string {
  return url.replace('sz=w800-h800', 'sz=w1600-h1600');
}

export default function ImageLightbox({ images, initialIndex, onClose }: ImageLightboxProps) {
  const sorted = [...images].sort((a, b) => a.position - b.position);
  const [index, setIndex] = useState(Math.min(initialIndex, sorted.length - 1));

  const prev = () => setIndex((i) => Math.max(0, i - 1));
  const next = () => setIndex((i) => Math.min(sorted.length - 1, i + 1));

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') setIndex((i) => Math.max(0, i - 1));
      else if (e.key === 'ArrowRight') setIndex((i) => Math.min(sorted.length - 1, i + 1));
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose, sorted.length]);

  if (sorted.length === 0) return null;

  const current = sorted[index];

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/90"
      onClick={onClose}
    >
      {/* Close button */}
      <button
        className="absolute top-4 right-4 text-white/70 hover:text-white transition-colors p-2 rounded-full bg-black/40 hover:bg-black/60"
        onClick={onClose}
        aria-label="Close"
      >
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Left arrow */}
      {index > 0 && (
        <button
          className="absolute left-4 top-1/2 -translate-y-1/2 text-white/70 hover:text-white transition-colors p-2 rounded-full bg-black/40 hover:bg-black/60"
          onClick={(e) => { e.stopPropagation(); prev(); }}
          aria-label="Previous image"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Image */}
      <div
        className="flex items-center justify-center max-w-screen-lg max-h-[85vh] px-16"
        onClick={(e) => e.stopPropagation()}
      >
        <img
          key={current.id}
          src={fullResUrl(current.url)}
          alt={`Image ${index + 1}`}
          className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl transition-opacity duration-200"
        />
      </div>

      {/* Counter */}
      {sorted.length > 1 && (
        <div className="mt-4 text-white/60 text-sm select-none">
          {index + 1} / {sorted.length}
        </div>
      )}

      {/* Right arrow */}
      {index < sorted.length - 1 && (
        <button
          className="absolute right-4 top-1/2 -translate-y-1/2 text-white/70 hover:text-white transition-colors p-2 rounded-full bg-black/40 hover:bg-black/60"
          onClick={(e) => { e.stopPropagation(); next(); }}
          aria-label="Next image"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}
    </div>
  );
}
