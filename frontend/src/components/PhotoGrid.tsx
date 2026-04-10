interface PhotoGridProps {
  images: Array<{ id: string; url: string; position: number }>;
  onImageClick?: (index: number) => void;
}

export default function PhotoGrid({ images, onImageClick }: PhotoGridProps) {
  if (!images || images.length === 0) return null;

  const sorted = [...images].sort((a, b) => a.position - b.position);
  const count = sorted.length;

  const imgClass = () =>
    `w-full h-full object-cover${onImageClick ? ' cursor-pointer' : ''}`;

  const imgEl = (img: (typeof sorted)[number], idx: number, extraClass = '') => (
    <div
      key={img.id}
      className={`relative overflow-hidden group ${extraClass}`}
      onClick={() => onImageClick?.(idx)}
    >
      <img
        src={img.url}
        alt={`Post image ${img.position + 1}`}
        loading="lazy"
        className={imgClass()}
      />
      {onImageClick && (
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
          <svg
            className="w-6 h-6 text-white opacity-0 group-hover:opacity-80 transition-opacity"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
          </svg>
        </div>
      )}
    </div>
  );

  if (count === 1) {
    return (
      <div className="rounded-xl overflow-hidden max-h-80">
        <img
          src={sorted[0].url}
          alt="Post image 1"
          loading="lazy"
          className={`w-full max-h-80 object-cover${onImageClick ? ' cursor-pointer' : ''}`}
          onClick={() => onImageClick?.(0)}
        />
      </div>
    );
  }

  if (count === 2) {
    return (
      <div className="flex gap-0.5 rounded-xl overflow-hidden h-48">
        {sorted.map((img, idx) =>
          imgEl(img, idx, 'flex-1'),
        )}
      </div>
    );
  }

  if (count === 3) {
    return (
      <div className="flex gap-0.5 rounded-xl overflow-hidden h-48">
        {imgEl(sorted[0], 0, 'flex-1')}
        <div className="flex flex-col gap-0.5 flex-1">
          {imgEl(sorted[1], 1, 'flex-1')}
          {imgEl(sorted[2], 2, 'flex-1')}
        </div>
      </div>
    );
  }

  // 4 images: 2×2 grid
  return (
    <div className="grid grid-cols-2 gap-0.5 rounded-xl overflow-hidden h-64">
      {sorted.map((img, idx) => imgEl(img, idx))}
    </div>
  );
}
