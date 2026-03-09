import React, { useState } from 'react'
import { Search, ShieldCheck } from 'lucide-react'

interface Props {
  onSubmit: (target: string, disease: string) => void
  loading?: boolean
}

export function SearchBar({ onSubmit, loading }: Props) {
  const [target, setTarget] = useState('')
  const [disease, setDisease] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (target.trim() && disease.trim()) {
      onSubmit(target.trim(), disease.trim())
    }
  }

  return (
    <div className="w-full max-w-2xl mx-auto space-y-4">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <label className="label-mono block mb-1.5 pl-1">Target gene / protein</label>
            <input
              type="text"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="e.g. KRAS G12C, BACE1, PCSK9"
              className="w-full bg-white border border-border rounded-lg px-4 py-3 text-sm
                         text-ink placeholder-ink-4 font-mono
                         focus:outline-none focus:border-teal focus:ring-1 focus:ring-teal/30
                         transition-colors"
              disabled={loading}
            />
          </div>
          <div className="flex-1 relative">
            <label className="label-mono block mb-1.5 pl-1">Disease / indication</label>
            <input
              type="text"
              value={disease}
              onChange={(e) => setDisease(e.target.value)}
              placeholder="e.g. non-small cell lung cancer"
              className="w-full bg-white border border-border rounded-lg px-4 py-3 text-sm
                         text-ink placeholder-ink-4
                         focus:outline-none focus:border-teal focus:ring-1 focus:ring-teal/30
                         transition-colors"
              disabled={loading}
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || !target.trim() || !disease.trim()}
          className="btn-primary w-full flex items-center justify-center gap-2 py-3 rounded-lg
                     font-semibold text-sm
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors"
        >
          <Search size={16} />
          {loading ? 'Evaluating…' : 'Evaluate Target'}
        </button>
      </form>

      {/* Privacy notice */}
      <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-surface-2 border border-border">
        <ShieldCheck size={14} className="text-ink-3 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-ink-3 leading-relaxed">
          <span className="text-ink-2 font-medium">Query privacy:</span> Target-disease pairs are not logged,
          stored, or shared. All queries are ephemeral and processed in real-time.
        </p>
      </div>
    </div>
  )
}
