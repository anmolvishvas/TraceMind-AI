import { FC, useState, useEffect, type FormEvent } from "react";
import {
  Search,
  BookOpen,
  FileText,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import { KnowledgeDocument, SemanticSearchResult } from "../types";
import { fetchDocuments, searchKnowledgeBase } from "../api/client";

export const KnowledgeBaseView: FC = () => {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<SemanticSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [hasSearched, setHasSearched] = useState<boolean>(false);

  useEffect(() => {
    fetchDocuments().then(setDocuments);
  }, []);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setHasSearched(true);
    try {
      const results = await searchKnowledgeBase(searchQuery);
      setSearchResults(results);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Semantic Search Banner */}
      <div className="bg-gradient-to-r from-violet-950/40 via-[#111827] to-cyan-950/30 border border-violet-500/30 rounded-xl p-6 shadow-xl">
        <div className="max-w-2xl space-y-2">
          <div className="flex items-center space-x-2 text-violet-400 text-xs font-bold uppercase tracking-wider">
            <Sparkles className="w-4 h-4" />
            <span>PostgreSQL pgvector Semantic Search Engine</span>
          </div>
          <h2 className="text-xl font-bold text-white">
            Historical Incident & Runbook Knowledge Base
          </h2>
          <p className="text-xs text-gray-300 leading-relaxed">
            Query past post-mortems, architecture recovery playbooks, and mitigation procedures using 1536-dimensional HNSW embeddings.
          </p>

          <form onSubmit={handleSearch} className="pt-2 flex items-center space-x-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search runbooks, e.g. 'PostgreSQL connection starvation' or 'Redis latency'..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#1A2333] border border-gray-700 rounded-lg pl-9 pr-3.5 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-violet-500"
              />
            </div>
            <button
              type="submit"
              disabled={isSearching || !searchQuery.trim()}
              className="px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white font-bold rounded-lg text-xs shadow transition flex-shrink-0"
            >
              {isSearching ? "Searching..." : "Vector Search"}
            </button>
          </form>
        </div>
      </div>

      {/* Semantic Search Results (if searched) */}
      {hasSearched && (
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center space-x-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Semantic Search Matches ({searchResults.length} Results)</span>
            </h3>
            <span className="text-[11px] font-mono text-gray-400">Cosine Similarity &gt; 0.40</span>
          </div>

          {searchResults.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-400">
              No matching knowledge chunks found. Try expanding query terms.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {searchResults.map((result) => (
                <div
                  key={result.chunk_id}
                  className="bg-[#161F30] border border-gray-700/60 rounded-xl p-4 space-y-2 hover:border-violet-500/40 transition"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white">{result.title}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-violet-500/20 text-violet-300 border border-violet-500/30">
                      Score: {(result.similarity_score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <p className="text-xs text-gray-300 leading-relaxed font-sans">{result.content}</p>
                  <div className="pt-2 border-t border-gray-800 flex items-center justify-between text-[10px] text-gray-500 font-mono">
                    <span>Chunk ID: {result.chunk_id}</span>
                    <span>Doc: {result.document_id}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Indexed Runbooks & Documentation Table */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-xs text-gray-400">
            <BookOpen className="w-4 h-4 text-violet-400" />
            <span className="font-semibold text-white">Indexed Knowledge Documents</span>
            <span>({documents.length} playbooks indexed)</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#161F30] text-gray-400 font-medium border-b border-gray-800">
              <tr>
                <th className="px-5 py-3">Document Title</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Source Path</th>
                <th className="px-5 py-3">Chunks</th>
                <th className="px-5 py-3">Indexed On</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-mono">
              {documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-[#1E293B]/30 transition">
                  <td className="px-5 py-3.5 font-sans font-medium text-white flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                    <span>{doc.title}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-800 border border-gray-700 text-gray-300">
                      {doc.document_type}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-gray-400 text-[11px]">{doc.source}</td>
                  <td className="px-5 py-3.5 text-cyan-400 font-bold">{doc.chunk_count}</td>
                  <td className="px-5 py-3.5 text-gray-400 text-[11px]">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
