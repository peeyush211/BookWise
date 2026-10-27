import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MLInsightsPage from '../pages/MLInsightsPage';
import { api } from '../services/api';

vi.mock('../services/api', () => ({ api: {
  getEvaluationMetrics: vi.fn(), getClusterOverview: vi.fn(), getUserCluster: vi.fn(), predictGenres: vi.fn(),
} }));

beforeEach(() => {
  vi.clearAllMocks();
  api.getEvaluationMetrics.mockResolvedValue({
    evaluation_scope: { ranking_users_evaluated: 12 },
    metrics_summary: {
      Popularity: { 'Precision@5': 0.1, 'Recall@10': 0.05, 'NDCG@10': 0.2, RMSE: 1.1, Catalog_Coverage_Pct: 2 },
      Hybrid: { 'Precision@5': 0.2, 'Recall@10': 0.1, 'NDCG@10': 0.4, RMSE: 0.8, Catalog_Coverage_Pct: 12 },
    },
  });
  api.getClusterOverview.mockResolvedValue({ clusters: [{ cluster_id: 0, label: 'Fantasy readers', users: 3 }] });
  api.getUserCluster.mockResolvedValue({ model: 'K-Means', cluster_count: 1, cluster_label: 'Fantasy readers', users_in_cluster: 3, top_genres: [{ genre: 'Fantasy' }] });
  api.predictGenres.mockResolvedValue({
    model: 'TF-IDF + calibrated Logistic Regression',
    status: 'confident',
    confidence_note: 'Calibrated estimated probability.',
    matched_signals: ['Fantasy'],
    unknown_tags: ['wyrdcore'],
    predictions: [{ genre: 'Fantasy', confidence: 0.91, confidence_status: 'confident' }],
    multilabel: { predictions: [{ genre: 'Fantasy', confidence: 0.91, confidence_status: 'confident' }] },
  });
});

describe('ML insights page', () => {
  it('shows the winning model, charts, clustering, and genre prediction', async () => {
    render(<MLInsightsPage currentUser={{ id: 1 }} onSignIn={vi.fn()} />);
    expect((await screen.findAllByText('Hybrid')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Fantasy readers').length).toBeGreaterThan(0);
    expect(screen.getByText('12 sampled evaluation users')).toBeInTheDocument();
    expect(screen.getByText('Clusters among app readers')).toBeInTheDocument();
    expect(screen.getByText('Shared by 3 app readers · K-Means')).toBeInTheDocument();
    expect(screen.getByText('Fantasy readers · Group 1')).toBeInTheDocument();
    expect(screen.getByText('Enter a book title. Add tags for a more accurate prediction.')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('Book title'), { target: { value: 'A dragon kingdom' } });
    fireEvent.click(screen.getByRole('button', { name: 'Predict genres' }));
    await waitFor(() => expect(api.predictGenres).toHaveBeenCalledWith(expect.objectContaining({ title: 'A dragon kingdom' })));
    expect(await screen.findByText('91%')).toBeInTheDocument();
    expect(screen.getAllByText('Confident estimate').length).toBeGreaterThan(0);
    expect(screen.getByText(/Unrecognized tags: wyrdcore/)).toBeInTheDocument();
    expect(screen.getByText('Multi-genre signals')).toBeInTheDocument();
  });
});
