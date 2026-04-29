import { useState, useCallback, useRef } from 'react';
import type { ImportSummaryResponse } from '../types';
import { importLocations, importFeatures } from '../api/client';

interface ImportModalProps {
  onClose: () => void;
  onImportSuccess: () => void;
}

type TabType = 'locations' | 'features';

interface ParsedFile {
  records: any[];
  raw: any;
}

function parseFile(content: string, tab: TabType): ParsedFile | null {
  try {
    const parsed = JSON.parse(content);
    if (tab === 'locations') {
      if (Array.isArray(parsed)) {
        return { records: parsed, raw: parsed };
      } else if (parsed && typeof parsed === 'object') {
        if (Array.isArray(parsed.locations)) {
          return { records: parsed.locations, raw: parsed };
        } else if (Array.isArray(parsed.mines)) {
          return { records: parsed.mines, raw: parsed };
        }
      }
      return null;
    } else {
      if (parsed.type !== 'FeatureCollection' || !Array.isArray(parsed.features)) return null;
      return { records: parsed.features, raw: parsed };
    }
  } catch {
    return null;
  }
}

function LocationPreviewRow({ rec, index }: { rec: any; index: number }) {
  return (
    <tr className={index % 2 === 0 ? 'bg-stone-50' : ''}>
      <td className="px-3 py-1.5 text-xs text-stone-700 truncate max-w-[140px]">{rec.name ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-stone-500">{rec.type ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-stone-500 font-mono">{rec.latitude ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-stone-500 font-mono">{rec.longitude ?? '—'}</td>
    </tr>
  );
}

function FeaturePreviewRow({ rec, index }: { rec: any; index: number }) {
  const coordCount = rec?.geometry?.coordinates?.length ?? 0;
  return (
    <tr className={index % 2 === 0 ? 'bg-stone-50' : ''}>
      <td className="px-3 py-1.5 text-xs text-stone-700 truncate max-w-[140px]">{rec?.properties?.name ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-stone-500">{rec?.properties?.type ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-stone-500">{coordCount} pts</td>
    </tr>
  );
}

export default function ImportModal({ onClose, onImportSuccess }: ImportModalProps) {
  const [tab, setTab] = useState<TabType>('locations');
  const [parsedFile, setParsedFile] = useState<ParsedFile | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [summary, setSummary] = useState<ImportSummaryResponse | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileContent = useCallback((content: string) => {
    setParseError(null);
    setSummary(null);
    setImportError(null);
    const result = parseFile(content, tab);
    if (!result) {
      setParseError(
        tab === 'locations'
          ? 'Invalid format: expected a JSON array of location objects.'
          : 'Invalid format: expected a GeoJSON FeatureCollection with LineString features.',
      );
      setParsedFile(null);
    } else {
      setParsedFile(result);
    }
  }, [tab]);

  const handleFile = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => handleFileContent(e.target?.result as string);
    reader.readAsText(file);
  }, [handleFileContent]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleTabChange = useCallback((newTab: TabType) => {
    setTab(newTab);
    setParsedFile(null);
    setParseError(null);
    setSummary(null);
    setImportError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleImport = useCallback(async () => {
    if (!parsedFile) return;
    setIsImporting(true);
    setImportError(null);
    setSummary(null);
    try {
      const result =
        tab === 'locations'
          ? await importLocations(parsedFile.raw)
          : await importFeatures(parsedFile.raw);
      setSummary(result);
      if (result.inserted > 0) onImportSuccess();
    } catch (err: any) {
      setImportError(err?.response?.data?.detail ?? err?.message ?? 'Import failed');
    } finally {
      setIsImporting(false);
    }
  }, [parsedFile, tab, onImportSuccess]);

  const previewRecords = parsedFile ? parsedFile.records.slice(0, 10) : [];
  const totalRecords = parsedFile ? parsedFile.records.length : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white border border-stone-200 rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200">
          <h2 className="text-stone-900 font-semibold text-base">Import Data</h2>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-stone-700 transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-stone-200 px-6">
          {(['locations', 'features'] as TabType[]).map((t) => (
            <button
              key={t}
              onClick={() => handleTabChange(t)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
                tab === t
                  ? 'border-amber-600 text-amber-700'
                  : 'border-transparent text-stone-500 hover:text-stone-700'
              }`}
            >
              {t === 'locations' ? 'Locations' : 'Linear Features'}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Format hint */}
          <p className="text-xs text-stone-500">
            {tab === 'locations'
              ? 'Upload a .json file containing a flat array of location objects, or a nested object with a "locations" or "mines" array (name, type, latitude, longitude, …).'
              : 'Upload a .geojson file with a FeatureCollection of LineString features (name + type in properties).'}
          </p>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
              isDragging
                ? 'border-amber-500 bg-amber-50'
                : 'border-stone-300 hover:border-stone-400 hover:bg-stone-50'
            }`}
          >
            <svg
              className="w-8 h-8 mx-auto mb-2 text-stone-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5-5m0 0l5 5m-5-5v12"
              />
            </svg>
            <p className="text-sm text-stone-500">
              Drag &amp; drop a file here, or <span className="text-amber-700 underline">click to browse</span>
            </p>
            <p className="text-xs text-stone-400 mt-1">Accepts .json and .geojson</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.geojson"
              className="hidden"
              onChange={handleFileInput}
            />
          </div>

          {/* Parse error */}
          {parseError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {parseError}
            </div>
          )}

          {/* Preview */}
          {parsedFile && (
            <div>
              <p className="text-xs text-stone-500 mb-2">
                Found <span className="text-stone-900 font-semibold">{totalRecords}</span> record{totalRecords !== 1 ? 's' : ''} in file
                {totalRecords > 10 && <span className="text-stone-400"> — previewing first 10</span>}
              </p>
              <div className="border border-stone-200 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-stone-100">
                    <tr>
                      {tab === 'locations' ? (
                        <>
                          <th className="px-3 py-2 text-left text-xs font-medium text-stone-500">Name</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-stone-500">Type</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-stone-500">Lat</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-stone-500">Lon</th>
                        </>
                      ) : (
                        <>
                          <th className="px-3 py-2 text-left text-xs font-medium text-stone-500">Name</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-stone-500">Type</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-stone-500">Coords</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {previewRecords.map((rec, i) =>
                      tab === 'locations' ? (
                        <LocationPreviewRow key={i} rec={rec} index={i} />
                      ) : (
                        <FeaturePreviewRow key={i} rec={rec} index={i} />
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Import result summary */}
          {summary && (
            <div className="bg-stone-50 border border-stone-200 rounded-lg px-4 py-3 space-y-2">
              <p className="text-xs font-medium text-stone-600 uppercase tracking-wide">Import Result</p>
              <div className="flex flex-wrap gap-2">
                <span className="text-xs px-2.5 py-1 rounded-full bg-green-100 text-green-700 border border-green-200">
                  ✓ {summary.inserted} inserted
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-yellow-100 text-yellow-700 border border-yellow-200">
                  ⟳ {summary.skipped_duplicate} duplicate{summary.skipped_duplicate !== 1 ? 's' : ''} skipped
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-red-100 text-red-700 border border-red-200">
                  ✗ {summary.skipped_invalid} invalid skipped
                </span>
              </div>
              {summary.errors.length > 0 && (
                <div className="mt-1 space-y-0.5">
                  {summary.errors.map((err, i) => (
                    <p key={i} className="text-xs text-red-600">{err}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Import error */}
          {importError && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {importError}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-stone-200">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-stone-500 hover:text-stone-800 transition-colors"
          >
            Close
          </button>
          <button
            onClick={handleImport}
            disabled={!parsedFile || isImporting}
            className="px-5 py-2 text-sm font-medium text-white bg-stone-800 hover:bg-stone-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors flex items-center gap-2"
          >
            {isImporting && (
              <span className="w-3.5 h-3.5 border border-white border-t-transparent rounded-full animate-spin inline-block" />
            )}
            {isImporting ? 'Importing…' : 'Import'}
          </button>
        </div>
      </div>
    </div>
  );
}
