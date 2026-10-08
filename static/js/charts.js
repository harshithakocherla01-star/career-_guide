// Chart.js helper visualizations for TechTide Platform

const TechTideCharts = {
  radarChartInstance: null,
  historyChartInstance: null,
  adminBarChartInstance: null,

  // Render SVG Circular Progress Ring
  renderProgressRing(elementId, score) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const radius = 64;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;

    let strokeColor = '#2563eb';
    if (score >= 80) strokeColor = '#10b981';
    else if (score < 50) strokeColor = '#f59e0b';

    el.innerHTML = `
      <svg class="progress-ring-svg" width="160" height="160">
        <circle
          class="progress-ring-bg"
          stroke-width="12"
          fill="transparent"
          r="${radius}"
          cx="80"
          cy="80"
        />
        <circle
          class="progress-ring-val"
          stroke="${strokeColor}"
          stroke-width="12"
          stroke-dasharray="${circumference} ${circumference}"
          style="stroke-dashoffset: ${offset};"
          fill="transparent"
          r="${radius}"
          cx="80"
          cy="80"
        />
      </svg>
      <div class="progress-ring-text">
        <div class="progress-score-num">${score}%</div>
        <div class="progress-score-label">Readiness</div>
      </div>
    `;
  },

  // Render Radar Chart for Skills Comparison
  renderRadarChart(canvasId, labels, userLevels, reqLevels) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (this.radarChartInstance) {
      this.radarChartInstance.destroy();
    }

    const ctx = canvas.getContext('2d');
    this.radarChartInstance = new Chart(ctx, {
      type: 'radar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Your Current Level',
            data: userLevels,
            backgroundColor: 'rgba(37, 99, 235, 0.2)',
            borderColor: 'rgba(37, 99, 235, 1)',
            pointBackgroundColor: 'rgba(37, 99, 235, 1)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgba(37, 99, 235, 1)'
          },
          {
            label: 'Required Role Level',
            data: reqLevels,
            backgroundColor: 'rgba(16, 185, 129, 0.15)',
            borderColor: 'rgba(16, 185, 129, 0.9)',
            borderDash: [4, 4],
            pointBackgroundColor: 'rgba(16, 185, 129, 1)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgba(16, 185, 129, 1)'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            angleLines: { color: 'rgba(0, 0, 0, 0.08)' },
            grid: { color: 'rgba(0, 0, 0, 0.08)' },
            suggestedMin: 0,
            suggestedMax: 5,
            ticks: {
              stepSize: 1,
              backdropColor: 'transparent',
              font: { size: 10 }
            },
            pointLabels: {
              font: { size: 11, weight: '600' }
            }
          }
        },
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 12, padding: 14 }
          }
        }
      }
    });
  },

  // Render Line Chart for History
  renderHistoryChart(canvasId, dates, scores) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (this.historyChartInstance) {
      this.historyChartInstance.destroy();
    }

    const ctx = canvas.getContext('2d');
    this.historyChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: [{
          label: 'Career Readiness Score (%)',
          data: scores,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.08)',
          fill: true,
          tension: 0.3,
          pointBackgroundColor: '#2563eb',
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: { stepSize: 20 },
            grid: { color: 'rgba(0, 0, 0, 0.05)' }
          },
          x: {
            grid: { display: false }
          }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  },

  // Render Admin Bar Chart for Missing Skills
  renderAdminBarChart(canvasId, labels, counts) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (this.adminBarChartInstance) {
      this.adminBarChartInstance.destroy();
    }

    const ctx = canvas.getContext('2d');
    this.adminBarChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Candidate Count Deficient',
          data: counts,
          backgroundColor: 'rgba(239, 68, 68, 0.75)',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            ticks: { stepSize: 1 },
            grid: { color: 'rgba(0, 0, 0, 0.05)' }
          },
          x: {
            grid: { display: false }
          }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }
};
