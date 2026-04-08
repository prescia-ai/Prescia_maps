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
      if (!Array.isArray(parsed)) return null;
      return { records: parsed, raw: parsed };
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
    <tr className={index % 2 === 0 ? 'bg-slate-800/40' : ''}>
      <td className="px-3 py-1.5 text-xs text-slate-200 truncate max-w-[140px]">{rec.name ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-slate-400">{rec.type ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-slate-400 font-mono">{rec.latitude ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-slate-400 font-mono">{rec.longitude ?? '—'}</td>
    </tr>
  );
}

function FeaturePreviewRow({ rec, index }: { rec: any; index: number }) {
  const coordCount = rec?.geometry?.coordinates?.length ?? 0;
  return (
    <tr className={index % 2 === 0 ? 'bg-slate-800/40' : ''}>
      <td className="px-3 py-1.5 text-xs text-slate-200 truncate max-w-[140px]">{rec?.properties?.name ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-slate-400">{rec?.properties?.type ?? '—'}</td>
      <td className="px-3 py-1.5 text-xs text-slate-400">{coordCount} pts</td>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <h2 className="text-white font-semibold text-base">Import Data</h2>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-white transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700 px-6">
          {(['locations', 'features'] as TabType[]).map((t) => (
            <button
              key={t}
              onClick={() => handleTabChange(t)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
                tab === t
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {t === 'locations' ? 'Locations' : 'Linear Features'}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Format hint */}
          <p className="text-xs text-slate-500">
            {tab === 'locations'
              ? 'Upload a .json file containing an array of location objects (name, type, latitude, longitude, …).'
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
                ? 'border-blue-500 bg-blue-900/20'
                : 'border-slate-600 hover:border-slate-500 hover:bg-slate-800/40'
            }`}
          >
            <svg
              className="w-8 h-8 mx-auto mb-2 text-slate-500"
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
            <p className="text-sm text-slate-400">
              Drag &amp; drop a file here, or <span className="text-blue-400 underline">click to browse</span>
            </p>
            <p className="text-xs text-slate-600 mt-1">Accepts .json and .geojson</p>
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
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg px-4 py-3 text-sm text-red-300">
              {parseError}
            </div>
          )}

          {/* Preview */}
          {parsedFile && (
            <div>
              <p className="text-xs text-slate-400 mb-2">
                Found <span className="text-white font-semibold">{totalRecords}</span> record{totalRecords !== 1 ? 's' : ''} in file
                {totalRecords > 10 && <span className="text-slate-500"> — previewing first 10</span>}
              </p>
              <div className="border border-slate-700 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-slate-800">
                    <tr>
                      {tab === 'locations' ? (
                        <>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Name</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Type</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Lat</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Lon</th>
                        </>
                      ) : (
                        <>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Name</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Type</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Coords</th>
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
            <div className="bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-3 space-y-2">
              <p className="text-xs font-medium text-slate-300 uppercase tracking-wide">Import Result</p>
              <div className="flex flex-wrap gap-2">
                <span className="text-xs px-2.5 py-1 rounded-full bg-green-900/50 text-green-300 border border-green-700/50">
                  ✓ {summary.inserted} inserted
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-yellow-900/50 text-yellow-300 border border-yellow-700/50">
                  ⟳ {summary.skipped_duplicate} duplicate{summary.skipped_duplicate !== 1 ? 's' : ''} skipped
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-red-900/50 text-red-300 border border-red-700/50">
                  ✗ {summary.skipped_invalid} invalid skipped
                </span>
              </div>
              {summary.errors.length > 0 && (
                <div className="mt-1 space-y-0.5">
                  {summary.errors.map((err, i) => (
                    <p key={i} className="text-xs text-red-400">{err}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Import error */}
          {importError && (
            <div className="bg-red-900/30 border border-red-700/50 rounded-lg px-4 py-3 text-sm text-red-300">
              {importError}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-700">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            Close
          </button>
          <button
            onClick={handleImport}
            disabled={!parsedFile || isImporting}
            className="px-5 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-2"
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
