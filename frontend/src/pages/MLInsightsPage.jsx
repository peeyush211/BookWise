import { useCallback, useEffect, useMemo, useState } from 'react';
import { Brain, CheckCircle2, GitCompareArrows, Layers3, Sparkles, WandSparkles } from 'lucide-react';
import { api } from '../services/api';

const panel = 'rounded-2xl border border-[#E8DFC8] bg-white p-5 shadow-sm';
const input = 'w-full rounded-lg border border-[#D8CEBD] bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#C5A059]';
const button = 'rounded-lg bg-[#1E1B18] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#3D342A] disabled:cursor-not-allowed disabled:opacity-50';
const metricKeys = [
  ['Precision@5', 'Precision@5', 'higher'],
  ['Recall@10', 'Recall@10', 'higher'],
  ['NDCG@10', 'NDCG@10', 'higher'],
  ['RMSE', 'RMSE', 'lower'],
  ['Catalog_Coverage_Pct', 'Coverage %', 'higher'],
];

function numeric(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function MetricBar({ value, max, color = 'bg-[#C5A059]' }) {
  const width = max > 0 ? Math.max(3, Math.min(100, (value / max) * 100)) : 0;
  return <div className="h-2 overflow-hidden rounded-full bg-[#F2ECE1]"><div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} /></div>;
}

function confidenceLabel(status) {
  if (status === 'confident') return 'Confident estimate';
  if (status === 'estimated') return 'Estimated result';
  return 'Uncertain result';
}

export default function MLInsightsPage({ currentUser, onSignIn }) {
  const [metrics, setMetrics] = useState(null);
  const [clusters, setClusters] = useState(null);
  const [userCluster, setUserCluster] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [genreForm, setGenreForm] = useState({ title: '', authors: '', tags: '' });
  const [genreResult, setGenreResult] = useState(null);
  const [genreLoading, setGenreLoading] = useState(false);
  const [genreError, setGenreError] = useState('');

  const loadInsights = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [metricResult, clusterResult, currentCluster] = await Promise.all([
        api.getEvaluationMetrics(),
        api.getClusterOverview(),
        currentUser?.id ? api.getUserCluster(currentUser.id) : Promise.resolve(null),
      ]);
      setMetrics(metricResult);
      setClusters(clusterResult);
      setUserCluster(currentCluster);
    } catch (failure) {
      setError(failure.message || 'ML insights are temporarily unavailable.');
    } finally {
      setLoading(false);
    }
  }, [currentUser]);

  useEffect(() => { queueMicrotask(loadInsights); }, [loadInsights]);

  const summary = metrics?.metrics_summary || {};
  const modelRows = Object.entries(summary);
  const bestModel = useMemo(() => {
    if (!modelRows.length) return null;
    const score = ([, values]) => {
      const precision = numeric(values['Precision@5']) || 0;
      const recall = numeric(values['Recall@10']) || 0;
      const ndcg = numeric(values['NDCG@10']) || 0;
      const rmse = numeric(values.RMSE);
      return precision + recall + ndcg + (rmse === null ? 0 : Math.max(0, 1 - rmse / 5));
    };
    return modelRows.reduce((best, row) => score(row) > score(best) ? row : best, modelRows[0]);
  }, [modelRows]);

  const submitGenrePrediction = async (event) => {
    event.preventDefault();
    setGenreLoading(true);
    setGenreError('');
    try {
      setGenreResult(await api.predictGenres(genreForm));
    } catch (failure) {
      setGenreError(failure.message || 'Genre prediction failed.');
    } finally {
      setGenreLoading(false);
    }
  };

  return (
    <div className="space-y-8 pb-16">
      <header className="rounded-2xl border border-[#C5A059]/40 bg-gradient-to-r from-[#211A13] via-[#2D2319] to-[#1E1710] p-6 text-[#FAF7F2] shadow-xl sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[#C5A059]/40 bg-[#C5A059]/20 px-3 py-1 text-xs text-[#D4AF37]"><Brain size={14} /> ML Evaluation & Insights</div>
            <h1 className="font-serif text-3xl font-bold sm:text-4xl">Understand how BookWise learns</h1>
            <p className="mt-2 max-w-2xl text-sm text-[#CFC2B0]">Compare recommendation quality, predict a book&apos;s likely genres, and see how reading taste clusters improve personalization.</p>
          </div>
          {bestModel && <div className="rounded-xl border border-[#C5A059]/30 bg-black/25 p-4 text-right"><p className="text-[10px] uppercase tracking-widest text-[#A6977F]">Best overall model</p><p className="mt-1 font-serif text-xl font-bold text-[#D4AF37]">{bestModel[0]}</p><p className="mt-1 text-xs text-[#CFC2B0]">Highest combined ranking quality</p></div>}
        </div>
      </header>

      {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}<button type="button" onClick={loadInsights} className="ml-3 underline">Retry</button></div>}
      {loading ? <div role="status" className={`${panel} py-12 text-center text-sm text-[#7A6D5A]`}>Loading evaluation and reader insights…</div> : <>
        <section className={panel} aria-labelledby="model-comparison-heading">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 id="model-comparison-heading" className="flex items-center gap-2 font-serif text-2xl font-bold"><GitCompareArrows size={20} className="text-[#9E7D3B]" />Recommendation model comparison</h2><p className="mt-1 text-sm text-[#7A6D5A]">Offline held-out evaluation across ranking quality, rating error, and catalogue reach.</p></div><span className="rounded-full bg-[#FAF5EB] px-3 py-1 text-xs font-medium text-[#8C7040]">{metrics?.evaluation_scope?.ranking_users_evaluated || metrics?.test_users_evaluated || '—'} sampled evaluation users</span></div>
          <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-xs"><thead><tr className="border-b border-[#E8DFC8] text-[10px] uppercase tracking-wider text-[#7A6D5A]"><th className="px-3 py-3">Model</th>{metricKeys.map(([, label]) => <th key={label} className="px-3 py-3 text-right">{label}</th>)}<th className="px-3 py-3 text-right">Status</th></tr></thead><tbody className="divide-y divide-[#F2ECE1]">{modelRows.map(([name, values]) => <tr key={name} className={name === bestModel?.[0] ? 'bg-[#FFF8EB]' : ''}><td className="px-3 py-4 font-serif font-bold text-[#1E1B18]">{name === bestModel?.[0] && <Sparkles size={14} className="mr-1 inline text-[#C5A059]" />}{name}</td>{metricKeys.map(([key]) => <td key={key} className="px-3 py-4 text-right font-mono text-[#57524D]">{numeric(values[key]) === null ? '—' : key === 'Catalog_Coverage_Pct' ? `${Number(values[key]).toFixed(2)}%` : Number(values[key]).toFixed(4)}</td>)}<td className="px-3 py-4 text-right">{name === bestModel?.[0] ? <span className="inline-flex items-center gap-1 font-semibold text-[#2D6A4F]"><CheckCircle2 size={14} /> Best</span> : <span className="text-[#9A8F80]">Benchmark</span>}</td></tr>)}</tbody></table></div>
        </section>

        <section className="grid gap-6 lg:grid-cols-2" aria-label="Metric charts">
          {['Precision@5', 'Recall@10', 'NDCG@10', 'Catalog_Coverage_Pct'].map((metric) => {
            const values = modelRows.map(([name, row]) => ({ name, value: numeric(row[metric]) || 0 }));
            const max = Math.max(...values.map((item) => item.value), 1);
            return <div key={metric} className={panel}><h3 className="font-serif text-lg font-bold">{metric === 'Catalog_Coverage_Pct' ? 'Catalogue coverage' : metric} chart</h3><div className="mt-4 space-y-3">{values.map((item) => <div key={item.name}><div className="mb-1 flex justify-between gap-3 text-xs"><span className="truncate text-[#57524D]">{item.name}</span><span className="font-mono font-semibold text-[#1E1B18]">{metric === 'Catalog_Coverage_Pct' ? `${item.value.toFixed(2)}%` : item.value.toFixed(4)}</span></div><MetricBar value={item.value} max={max} color={item.name === bestModel?.[0] ? 'bg-[#2D6A4F]' : 'bg-[#C5A059]'} /></div>)}</div></div>;
          })}
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <div className={panel}>
            <div className="flex items-center gap-2"><WandSparkles size={20} className="text-[#9E7D3B]" /><h2 className="font-serif text-2xl font-bold">Genre prediction</h2></div>
            <p className="mt-1 text-sm text-[#7A6D5A]">Predictions use the book title, author, and tags. The catalogue genre is the training target, never an input.</p>
            <p className="mt-3 text-xs text-[#6B6358]">Enter a book title. Add tags for a more accurate prediction.</p>
            <form onSubmit={submitGenrePrediction} className="mt-5 space-y-3">
              <input className={input} placeholder="Book title" value={genreForm.title} onChange={(event) => setGenreForm({ ...genreForm, title: event.target.value })} />
              <input className={input} placeholder="Author" value={genreForm.authors} onChange={(event) => setGenreForm({ ...genreForm, authors: event.target.value })} />
              <input className={input} placeholder="Tags (fantasy, magic, dragons…)" value={genreForm.tags} onChange={(event) => setGenreForm({ ...genreForm, tags: event.target.value })} />
              <button className={button} disabled={genreLoading}>{genreLoading ? 'Predicting…' : 'Predict genres'}</button>
            </form>
            {genreError && <p role="alert" className="mt-3 text-xs text-red-700">{genreError}</p>}
            {genreResult && <div className="mt-5 rounded-xl bg-[#FAF7F2] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-[#7A6D5A]">{genreResult.model}</p><span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-[#8C7040]">{confidenceLabel(genreResult.status)}</span></div>
              <p className="mt-2 text-xs text-[#6B6358]">{genreResult.confidence_note || 'Scores are estimated probabilities, not guarantees.'}</p>
              <div className="mt-3 space-y-2">{genreResult.predictions?.map((prediction) => <div key={prediction.genre} className="flex items-center justify-between gap-3 text-sm"><span className="font-semibold text-[#1E1B18]">{prediction.genre}<span className="ml-2 text-[10px] font-normal uppercase tracking-wide text-[#8C7040]">{confidenceLabel(prediction.confidence_status)}</span></span><span className="font-mono text-[#9E7D3B]">{Math.round(prediction.confidence * 100)}%</span></div>)}</div>
              {genreResult.multilabel?.predictions?.length > 0 && <div className="mt-4 border-t border-[#E8DFC8] pt-3"><p className="text-[10px] font-semibold uppercase tracking-wider text-[#8C7040]">Multi-genre signals</p><p className="mt-1 text-xs text-[#6B6358]">A separate multi-label model can return overlapping genres.</p><div className="mt-2 flex flex-wrap gap-2">{genreResult.multilabel.predictions.map((prediction) => <span key={prediction.genre} className="rounded-full border border-[#D8CEBD] bg-white px-2.5 py-1 text-xs">{prediction.genre} · {Math.round(prediction.confidence * 100)}%</span>)}</div></div>}
              {genreResult.matched_signals?.length > 0 && <p className="mt-3 text-xs text-[#6B6358]">Recognized signals: {genreResult.matched_signals.join(', ')}</p>}
              {genreResult.unknown_tags?.length > 0 && <p className="mt-2 rounded-lg border border-[#E8DFC8] bg-white p-2 text-xs text-[#6B6358]">Unrecognized tags: {genreResult.unknown_tags.join(', ')}. These were not treated as new genres.</p>}
            </div>}
          </div>

          <div className={panel}><div className="flex items-center gap-2"><Layers3 size={20} className="text-[#9E7D3B]" /><h2 className="font-serif text-2xl font-bold">User taste clustering</h2></div><p className="mt-1 text-sm text-[#7A6D5A]">K-Means groups app readers by the genres they rate highly. The active cluster becomes a soft signal in personalized feeds.</p>{currentUser && userCluster?.cluster_count > 0 ? <div className="mt-5 rounded-xl border border-[#E8DFC8] bg-[#FAF7F2] p-4"><p className="text-[10px] uppercase tracking-widest text-[#8C7040]">Your current reading profile</p><h3 className="mt-1 font-serif text-xl font-bold text-[#1E1B18]">{userCluster.cluster_label}</h3><p className="mt-1 text-xs text-[#7A6D5A]">Shared by {userCluster.users_in_cluster} app reader{userCluster.users_in_cluster === 1 ? '' : 's'} · {userCluster.model}</p><div className="mt-4 flex flex-wrap gap-2">{userCluster.top_genres?.map((item) => <span key={item.genre} className="rounded-full border border-[#D8CEBD] bg-white px-3 py-1 text-xs">{item.genre}</span>)}</div>{userCluster.notice && <p className="mt-4 text-xs text-[#6B6358]">{userCluster.notice}</p>}</div> : !currentUser ? <div className="mt-5 rounded-xl bg-[#FAF7F2] p-5 text-center"><p className="text-sm text-[#57524D]">Sign in to calculate your personal reading cluster.</p><button type="button" onClick={onSignIn} className={`${button} mt-4`}>Sign in</button></div> : <p className="mt-5 rounded-xl bg-[#FAF7F2] p-5 text-sm text-[#7A6D5A]">Rate three books to unlock your reading cluster.</p>}<div className="mt-5 border-t border-[#E8DFC8] pt-4"><p className="text-xs font-semibold uppercase tracking-wider text-[#8C7040]">Clusters among app readers</p><div className="mt-3 space-y-2">{(clusters?.clusters || []).map((cluster) => <div key={cluster.cluster_id} className="flex items-center justify-between rounded-lg bg-[#FAF7F2] px-3 py-2 text-sm"><span>{cluster.label} · Group {cluster.cluster_id + 1}</span><span className="font-mono text-xs text-[#7A6D5A]">{cluster.users} app reader{cluster.users === 1 ? '' : 's'}</span></div>)}{!clusters?.clusters?.length && <p className="text-xs text-[#7A6D5A]">Clusters will appear as app readers add ratings.</p>}</div></div></div>
        </section>
      </>}
    </div>
  );
}
