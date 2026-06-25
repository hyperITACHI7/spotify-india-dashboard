import { useState, useEffect } from 'react';
import axios from 'axios';
import { AlertCircle } from 'lucide-react';
import API_URL from '../config';

export default function FrustrationsTable() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API_URL}/api/discovery/frustrations`)
      .then(res => {
        setReviews(res.data.data);
        setLoading(false);
      })
      .catch(err => console.error(err));
  }, []);

  if (loading) return <p className="loading">Loading frustrations...</p>;

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <table className="table-container">
        <thead>
          <tr>
            <th style={{ width: '40px' }}>#</th>
            <th style={{ width: '120px' }}>Date</th>
            <th style={{ width: '80px' }}>Rating</th>
            <th>Review Text</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((r, i) => (
            <tr key={i} className="table-row">
              <td style={{ textAlign: 'center' }}>{i + 1}</td>
              <td>{r.date}</td>
              <td>⭐ {r.rating}</td>
              <td className="highlight-text" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={16} color="#e74c3c" />
                {r.text}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
