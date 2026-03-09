import { ShieldCheck, Lock, ExternalLink, AlertTriangle, Shield } from 'lucide-react'
import type { PointMeResponse, DrugPatentResult } from '../types'

interface Props {
  data: PointMeResponse
}

export function IPPanel({ data }: Props) {
  const { scientific_evidence } = data

  return (
    <div className="space-y-4">
      {/* IP landscape card */}
      <div className="card space-y-4">
        <div className="flex items-center gap-2">
          <Lock size={14} className="text-ink-2" />
          <p className="label-mono">IP landscape overview</p>
          <a
            href="https://www.accessdata.fda.gov/scripts/cder/ob/"
            target="_blank"
            rel="noopener noreferrer"
            className="source-chip ml-auto"
          >
            FDA Orange Book <ExternalLink size={9} />
          </a>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div>
            <p className="label-mono">Drugs in pipeline</p>
            <span className="font-mono text-2xl font-bold text-ink mt-1 block">
              {scientific_evidence.tractability.known_drugs_in_pipeline}
            </span>
          </div>
          <div>
            <p className="label-mono">Molecule type</p>
            <span className="font-mono text-sm text-ink-2 mt-1 block capitalize">
              {scientific_evidence.tractability.molecule_type.replace('_', ' ')}
            </span>
          </div>
          <div>
            <p className="label-mono">Tractability score</p>
            <div className="flex items-baseline gap-1 mt-1">
              <span className="font-mono text-2xl font-bold text-teal">
                {scientific_evidence.tractability.score.toFixed(2)}
              </span>
              <span className="text-ink-3 text-xs">/1.00</span>
            </div>
          </div>
        </div>

        {/* IP flag if any */}
        {data.flags.some((f) => f.type === 'ip_risk') && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-caution-light border border-caution-border">
            <AlertTriangle size={14} className="text-caution mt-0.5 flex-shrink-0" />
            <div>
              {data.flags
                .filter((f) => f.type === 'ip_risk')
                .map((f, idx) => (
                  <p key={idx} className="text-sm text-ink-2">{f.message}</p>
                ))}
            </div>
          </div>
        )}

        <p className="text-xs text-ink-3 leading-relaxed">
          IP landscape data sourced from the FDA Orange Book (patent and exclusivity listings) and Drugs@FDA
          (approved drug products). A full freedom-to-operate analysis requires a patent attorney review.
          <a
            href="https://www.accessdata.fda.gov/scripts/cder/ob/docs/queryai.cfm"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-1 text-teal underline hover:text-teal/80"
          >
            Orange Book search ↗
          </a>
        </p>
      </div>

      {/* Patent radar */}
      {data.patent_radar && (
        <div className="card space-y-4">
          <div className="flex items-center gap-2">
            <Shield size={14} className="text-ink-2" />
            <p className="label-mono">Patent radar — USPTO PatentsView scan</p>
            <a href="https://patentsview.org" target="_blank" rel="noopener noreferrer" className="source-chip ml-auto">
              PatentsView <ExternalLink size={9} />
            </a>
          </div>

          {/* Traffic light summary */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-nogo-light border border-nogo-border rounded-lg p-2 text-center">
              <p className="font-mono text-lg font-bold text-nogo">{data.patent_radar.red_count}</p>
              <p className="text-[10px] text-nogo font-mono uppercase tracking-wide">High risk</p>
            </div>
            <div className="bg-caution-light border border-caution-border rounded-lg p-2 text-center">
              <p className="font-mono text-lg font-bold text-caution">{data.patent_radar.yellow_count}</p>
              <p className="text-[10px] text-caution font-mono uppercase tracking-wide">Review needed</p>
            </div>
            <div className="bg-go-light border border-go-border rounded-lg p-2 text-center">
              <p className="font-mono text-lg font-bold text-go">
                {data.patent_radar.patents.length - data.patent_radar.red_count - data.patent_radar.yellow_count}
              </p>
              <p className="text-[10px] text-go font-mono uppercase tracking-wide">Low concern</p>
            </div>
          </div>

          {/* LLM summary */}
          <p className="text-sm text-ink-2 leading-relaxed">{data.patent_radar.summary}</p>

          {/* Individual patents */}
          {data.patent_radar.patents.length > 0 && (
            <div className="space-y-2">
              <p className="label-mono">Patents analyzed</p>
              {data.patent_radar.patents.map((patent, idx) => (
                <PatentCard key={idx} patent={patent} />
              ))}
            </div>
          )}

          {/* Disclaimer */}
          <p className="text-xs text-ink-4 italic border-t border-border pt-3">
            {data.patent_radar.disclaimer}
          </p>
        </div>
      )}

      {/* Privacy & security */}
      <div className="card space-y-3">
        <div className="flex items-center gap-2">
          <ShieldCheck size={14} className="text-go" />
          <p className="label-mono">Data privacy & security</p>
        </div>
        <div className="space-y-2.5">
          <PrivacyRow
            icon="🔒"
            title="Queries are ephemeral"
            desc="Target-disease pairs submitted to PointMe are not logged, stored in any database, or retained after the analysis completes."
          />
          <PrivacyRow
            icon="🌐"
            title="API calls are read-only"
            desc="PointMe only reads from public databases (Open Targets, ClinicalTrials.gov, PubMed, UniProt, FDA). No data is written to external systems."
          />
          <PrivacyRow
            icon="🧬"
            title="No IP exposure"
            desc="Evaluating a target name does not disclose your pipeline, compounds, or proprietary biology. The platform operates on gene/protein names from public databases."
          />
          <PrivacyRow
            icon="📋"
            title="Export controls"
            desc="Downloaded reports stay on your device. PointMe does not receive copies of exported assessments."
          />
        </div>
      </div>

      {/* Patent landscape note */}
      <div className="card space-y-3">
        <p className="label-mono">Next steps for IP diligence</p>
        <div className="space-y-2 text-sm text-ink-2 leading-relaxed">
          <p>
            PointMe's IP assessment covers{' '}
            <strong className="text-ink font-semibold">regulatory exclusivities</strong> (Orange Book listings, Orphan Drug exclusivity, NCE periods)
            and{' '}
            <strong className="text-ink font-semibold">approved drug precedent</strong> (Drugs@FDA).
          </p>
          <p>
            It does <strong className="text-ink font-semibold">not</strong> replace a full patent landscape search.
            Before advancing into development, we recommend:
          </p>
          <ul className="space-y-1 pl-4 text-xs text-ink-3">
            <li>→ Freedom-to-operate (FTO) analysis via{' '}
              <a href="https://patents.google.com" target="_blank" rel="noopener noreferrer" className="text-teal hover:underline">
                Google Patents ↗
              </a>
              {' '}or{' '}
              <a href="https://worldwide.espacenet.com" target="_blank" rel="noopener noreferrer" className="text-teal hover:underline">
                Espacenet ↗
              </a>
            </li>
            <li>→ Composition-of-matter patent search for your specific compounds</li>
            <li>→ Review of continuation and divisional patents around approved agents</li>
            <li>→ Patent expiry mapping to identify exclusivity windows</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

function PatentCard({ patent }: { patent: DrugPatentResult }) {
  const relevanceConfig = {
    red: { color: '#C1292E', bg: 'rgba(193,41,46,0.06)', border: 'rgba(193,41,46,0.25)', label: 'HIGH RISK' },
    yellow: { color: '#D4930D', bg: 'rgba(212,147,13,0.06)', border: 'rgba(212,147,13,0.25)', label: 'REVIEW' },
    green: { color: '#2D936C', bg: 'rgba(45,147,108,0.06)', border: 'rgba(45,147,108,0.25)', label: 'LOW RISK' },
  }
  const cfg = relevanceConfig[patent.relevance]

  return (
    <div className="rounded-lg border p-3 space-y-1.5" style={{ background: cfg.bg, borderColor: cfg.border }}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
              style={{ color: cfg.color, background: cfg.color + '18' }}
            >
              {cfg.label}
            </span>
            {!patent.is_active && (
              <span className="text-[10px] font-mono text-ink-4 bg-surface-3 border border-border px-1.5 py-0.5 rounded">
                EXPIRED
              </span>
            )}
            <span className="text-xs font-mono text-ink-4">{patent.patent_number}</span>
          </div>
          <p className="text-xs font-medium text-ink mt-1 leading-tight">{patent.title}</p>
        </div>
      </div>
      <p className="text-xs text-ink-3 leading-relaxed">{patent.relevance_explanation}</p>
      <div className="flex items-center gap-3 text-[10px] text-ink-4 font-mono">
        <span>{patent.assignee}</span>
        {patent.filing_date && <span>Filed: {patent.filing_date.slice(0, 4)}</span>}
        {patent.expiration_date && <span>Expires ~{patent.expiration_date.slice(0, 4)}</span>}
      </div>
      {patent.concerning_claims.length > 0 && (
        <div className="space-y-0.5 pt-1">
          {patent.concerning_claims.slice(0, 2).map((claim, i) => (
            <p key={i} className="text-[10px] text-ink-3 font-mono">⚠ {claim}</p>
          ))}
        </div>
      )}
    </div>
  )
}

function PrivacyRow({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-surface-2 border border-border">
      <span className="text-base flex-shrink-0">{icon}</span>
      <div>
        <p className="text-sm font-medium text-ink-2">{title}</p>
        <p className="text-xs text-ink-3 mt-0.5 leading-relaxed">{desc}</p>
      </div>
    </div>
  )
}
