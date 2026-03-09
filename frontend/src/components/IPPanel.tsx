import { ShieldCheck, Lock, ExternalLink, AlertTriangle } from 'lucide-react'
import type { PointMeResponse } from '../types'

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
