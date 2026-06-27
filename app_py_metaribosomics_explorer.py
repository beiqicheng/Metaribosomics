import React, { useMemo, useState } from "react";
import { Upload, Search, Database, LineChart as LineChartIcon, Download } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

function parseTSV(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return { header: [], rows: [] };
  const header = lines[0].split("\t");
  const samples = header.slice(2);
  const rows = lines.slice(1).map((line) => {
    const cols = line.split("\t");
    return {
      taxonomy: cols[0] ?? "",
      length: Number(cols[1] ?? 0),
      counts: cols.slice(2).map((v) => Number(v || 0)),
    };
  });
  return { header, samples, rows };
}

function fmt(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(n);
}

export default function LSUDatabaseBrowser() {
  const [fileName, setFileName] = useState("LSU-counts.txt");
  const [samples, setSamples] = useState([]);
  const [rows, setRows] = useState([]);
  const [query, setQuery] = useState("Metazoa");
  const [showOnlyMatches, setShowOnlyMatches] = useState(true);
  const [error, setError] = useState("");
  const [sampleFocus, setSampleFocus] = useState("All samples");

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setError("");
    const text = await file.text();
    const parsed = parseTSV(text);
    if (!parsed.rows.length) {
      setError("The file did not look like a valid tab-separated LSU table.");
      return;
    }
    setSamples(parsed.samples || []);
    setRows(parsed.rows);
    setSampleFocus("All samples");
  };

  const matched = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return rows.filter((r) => r.taxonomy.toLowerCase().includes(q));
  }, [rows, query]);

  const plotData = useMemo(() => {
    if (!matched.length || !samples.length) return [];
    return samples.map((sample, idx) => {
      let filtered = matched;
      if (sampleFocus !== "All samples") {
        const sampleIdx = samples.indexOf(sampleFocus);
        if (sampleIdx >= 0 && sample !== sampleFocus) return null;
      }
      const counts = filtered.map((r) => r.counts[idx] || 0);
      const total = counts.reduce((a, b) => a + b, 0);
      const weighted = total
        ? filtered.reduce((sum, r) => sum + r.length * (r.counts[idx] || 0), 0) / total
        : null;
      return {
        sample,
        weighted,
        totalCounts: total,
      };
    }).filter(Boolean);
  }, [matched, samples, sampleFocus]);

  const totals = useMemo(() => {
    if (!matched.length) return { rows: 0, counts: 0, weighted: null };
    let counts = 0;
    let weighted = 0;
    for (const r of matched) {
      const rc = r.counts.reduce((a, b) => a + b, 0);
      counts += rc;
      weighted += r.length * rc;
    }
    return {
      rows: matched.length,
      counts,
      weighted: counts ? weighted / counts : null,
    };
  }, [matched]);

  const downloadCSV = () => {
    if (!matched.length) return;
    const header = ["Sample", "WeightedLength_bp", "TotalCounts"];
    const lines = [header.join(",")].concat(
      plotData.map((d) => `${d.sample},${d.weighted ?? ""},${d.totalCounts}`)
    );
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${query.replace(/\s+/g, "_") || "taxon"}_weighted_length.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isReady = rows.length > 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-white text-slate-900">
      <div className="mx-auto max-w-7xl p-4 md:p-8">
        <div className="mb-6 flex flex-col gap-3 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200 md:p-6">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
                LSU Taxon Browser
              </h1>
              <p className="mt-1 text-sm text-slate-600">
                Upload the LSU-counts table, search any taxon, and the weighted LSU-length plot updates instantly.
              </p>
            </div>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-medium text-white shadow hover:bg-slate-800">
              <Upload className="h-4 w-4" />
              Upload TSV
              <input type="file" accept=".txt,.tsv,.csv" onChange={onUpload} className="hidden" />
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
                <Database className="h-4 w-4" /> Data file
              </div>
              <div className="text-sm text-slate-600">{fileName}</div>
              <div className="mt-1 text-xs text-slate-500">{rows.length ? `${rows.length} references loaded` : "No table loaded yet"}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
                <Search className="h-4 w-4" /> Search
              </div>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type a taxon, e.g. Metazoa"
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900"
              />
              <label className="mt-2 flex items-center gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={showOnlyMatches}
                  onChange={(e) => setShowOnlyMatches(e.target.checked)}
                  className="h-4 w-4"
                />
                Show only matching taxa in the results table
              </label>
            </div>
            <div className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
                <LineChartIcon className="h-4 w-4" /> Plot controls
              </div>
              <div className="text-xs text-slate-600">Selected taxon: <span className="font-medium">{query || "—"}</span></div>
              <div className="mt-2">
                <select
                  value={sampleFocus}
                  onChange={(e) => setSampleFocus(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900"
                >
                  <option>All samples</option>
                  {samples.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {error ? (
            <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200">
              {error}
            </div>
          ) : null}
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Weighted LSU rRNA length plot</h2>
                <p className="text-sm text-slate-600">
                  Weighted length = Σ(length × counts) / Σ(counts)
                </p>
              </div>
              <button
                onClick={downloadCSV}
                disabled={!matched.length}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Download className="h-4 w-4" /> Export CSV
              </button>
            </div>

            <div className="h-[460px] w-full">
              {isReady && matched.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={plotData} margin={{ top: 20, right: 20, left: 0, bottom: 60 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="sample" angle={-45} textAnchor="end" height={80} interval={0} />
                    <YAxis domain={["dataMin - 50", "dataMax + 50"]} />
                    <Tooltip
                      formatter={(value, name) => [fmt(value), name === "weighted" ? "Weighted length (bp)" : name]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="weighted"
                      name="Weighted length (bp)"
                      stroke="#1f4e78"
                      strokeWidth={3}
                      dot={{ r: 3 }}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
                  {isReady
                    ? "No matching taxa yet. Try a broader search such as 'Metazoa', 'Dinoflagellata', or 'Bacteria'."
                    : "Upload LSU-counts.txt to begin."}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
              <h2 className="text-lg font-semibold">Matched taxon summary</h2>
              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                  <div className="text-xs text-slate-500">Matched rows</div>
                  <div className="text-xl font-semibold">{fmt(totals.rows)}</div>
                </div>
                <div className="rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                  <div className="text-xs text-slate-500">Total counts</div>
                  <div className="text-xl font-semibold">{fmt(totals.counts)}</div>
                </div>
                <div className="col-span-2 rounded-2xl bg-slate-50 p-3 ring-1 ring-slate-200">
                  <div className="text-xs text-slate-500">Weighted length (all samples)</div>
                  <div className="text-xl font-semibold">{fmt(totals.weighted)} bp</div>
                </div>
              </div>
            </div>

            <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
              <h2 className="text-lg font-semibold">Quick examples</h2>
              <p className="mt-2 text-sm text-slate-600">
                Search examples: <span className="font-medium">Metazoa</span>, <span className="font-medium">Dinoflagellata</span>, <span className="font-medium">Chloroplast</span>, <span className="font-medium">Cyanobacteria</span>.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {["Metazoa", "Dinoflagellata", "Bacteria", "Archaea", "Chloroplast", "Cyanobacteria"].map((t) => (
                  <button
                    key={t}
                    onClick={() => setQuery(t)}
                    className="rounded-full border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:border-slate-900 hover:text-slate-900"
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
              <h2 className="text-lg font-semibold">Result table</h2>
              <div className="mt-3 max-h-[320px] overflow-auto rounded-2xl border border-slate-200">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 bg-slate-100 text-slate-700">
                    <tr>
                      <th className="px-3 py-2">Taxonomy</th>
                      <th className="px-3 py-2">Length</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(showOnlyMatches ? matched : rows).slice(0, 200).map((r, i) => (
                      <tr key={i} className="border-t border-slate-200">
                        <td className="px-3 py-2">{r.taxonomy}</td>
                        <td className="px-3 py-2">{r.length}</td>
                      </tr>
                    ))}
                    {!((showOnlyMatches ? matched : rows).length) ? (
                      <tr>
                        <td className="px-3 py-6 text-slate-500" colSpan={2}>
                          No rows to show.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <h2 className="text-lg font-semibold">How this works</h2>
          <p className="mt-2 text-sm text-slate-600 leading-6">
            The app reads the uploaded LSU table in the browser, filters rows whose taxonomy contains your search term,
            and calculates the weighted LSU reference length for each sample using the counts in that sample.
            This lets you type any taxon name and immediately see the corresponding weighted-length profile.
          </p>
        </div>
      </div>
    </div>
  );
}
