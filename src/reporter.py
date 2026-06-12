import os
import json
from jinja2 import Template
from typing import List, Dict, Any, Optional
from src.config import EvalRun, TestResult
from src.database import get_run_history

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Eval Report - Run #{{ run.id }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        darkBg: '#090d16',
                        darkCard: '#131a26',
                        accentViolet: '#8b5cf6',
                        accentIndigo: '#6366f1',
                    }
                }
            }
        }
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: #090d16;
            color: #f3f4f6;
        }
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Outfit', sans-serif;
        }
        .glass {
            background: rgba(19, 26, 38, 0.6);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
    </style>
</head>
<body class="p-6 md:p-12 min-h-screen">
    <div class="max-w-7xl mx-auto space-y-8">
        
        <!-- HEADER -->
        <header class="flex flex-col md:flex-row justify-between items-start md:items-center p-6 rounded-2xl glass shadow-2xl gap-4">
            <div class="space-y-1">
                <div class="flex items-center gap-3">
                    <span class="text-sm font-semibold uppercase tracking-wider text-accentViolet px-2.5 py-0.5 rounded-full bg-accentViolet/10">Pipeline Report</span>
                    <span class="text-gray-500">|</span>
                    <span class="text-sm text-gray-400">ID: {{ run.id }}</span>
                </div>
                <h1 class="text-3xl font-bold tracking-tight bg-gradient-to-r from-white via-gray-200 to-gray-500 bg-clip-text text-transparent">Model Regression Diagnostics</h1>
                <p class="text-gray-400 text-sm">Analyzed prompt version <code class="text-accentViolet bg-accentViolet/5 px-1.5 py-0.5 rounded">v{{ run.prompt_version }}</code> running on <code class="text-accentViolet bg-accentViolet/5 px-1.5 py-0.5 rounded">{{ run.model }}</code></p>
            </div>
            
            <div class="flex flex-col items-end gap-1.5">
                {% if status == 'CRITICAL' %}
                <div class="flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 font-semibold text-lg animate-pulse">
                    <span class="w-3 h-3 bg-red-500 rounded-full"></span>
                    CRITICAL REGRESSION
                </div>
                {% elif status == 'WARNING' %}
                <div class="flex items-center gap-2 px-4 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-xl text-yellow-400 font-semibold text-lg">
                    <span class="w-3 h-3 bg-yellow-500 rounded-full"></span>
                    WARNING (REGRESSION)
                </div>
                {% else %}
                <div class="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 font-semibold text-lg">
                    <span class="w-3 h-3 bg-emerald-500 rounded-full"></span>
                    TESTS PASSED
                </div>
                {% endif %}
                <span class="text-xs text-gray-500">Timestamp: {{ run.timestamp }}</span>
            </div>
        </header>

        <!-- DRIFT WARNING IF DETECTED -->
        {% if drift and drift.drift_detected %}
        <div class="flex items-start gap-4 p-5 rounded-2xl bg-yellow-500/10 border border-yellow-500/20 text-yellow-300">
            <span class="text-2xl mt-0.5">⚠️</span>
            <div class="space-y-1">
                <h3 class="font-semibold text-lg text-yellow-200">Slow Performance Drift Detected</h3>
                <p class="text-sm text-yellow-300/80">{{ drift.message }}</p>
                <div class="text-xs text-yellow-400/60 mt-1">Rolling Accuracy: {{ "%.1f"|format(drift.rolling_avg_pass_rate) }}% | Baseline: {{ "%.1f"|format(baseline.pass_rate) if baseline else 'N/A' }}% (Window: {{ drift.window_size }} runs)</div>
            </div>
        </div>
        {% endif %}

        <!-- METRICS COMPARATIVE CARD GRID -->
        <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <!-- Accuracy -->
            <div class="p-6 rounded-2xl glass shadow-lg space-y-4">
                <div class="flex justify-between items-center text-gray-400">
                    <span class="text-sm font-medium">Category Accuracy</span>
                    <span class="text-xl">🎯</span>
                </div>
                <div class="flex items-baseline gap-2">
                    <span class="text-4xl font-bold">{{ "%.1f"|format(run.pass_rate) }}%</span>
                    {% if baseline %}
                        {% set delta = run.pass_rate - baseline.pass_rate %}
                        {% if delta > 0 %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-full">+{{ "%.1f"|format(delta) }}%</span>
                        {% elif delta < 0 %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-red-500/10 text-red-400 rounded-full">{{ "%.1f"|format(delta) }}%</span>
                        {% else %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-gray-500/10 text-gray-400 rounded-full">0.0%</span>
                        {% endif %}
                    {% endif %}
                </div>
                <p class="text-xs text-gray-500">Baseline accuracy: {{ "%.1f"|format(baseline.pass_rate) if baseline else 'N/A' }}%</p>
            </div>

            <!-- Summary Relevance -->
            <div class="p-6 rounded-2xl glass shadow-lg space-y-4">
                <div class="flex justify-between items-center text-gray-400">
                    <span class="text-sm font-medium">Avg Summary Relevance</span>
                    <span class="text-xl">⚖️</span>
                </div>
                <div class="flex items-baseline gap-2">
                    <span class="text-4xl font-bold">{{ "%.2f"|format(run.avg_relevance) }}/5</span>
                    {% if baseline %}
                        {% set delta = run.avg_relevance - baseline.avg_relevance %}
                        {% if delta > 0 %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-full">+{{ "%.2f"|format(delta) }}</span>
                        {% elif delta < 0 %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-red-500/10 text-red-400 rounded-full">{{ "%.2f"|format(delta) }}</span>
                        {% else %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-gray-500/10 text-gray-400 rounded-full">0.00</span>
                        {% endif %}
                    {% endif %}
                </div>
                <p class="text-xs text-gray-500">Baseline score: {{ "%.2f"|format(baseline.avg_relevance) if baseline else 'N/A' }}/5</p>
            </div>

            <!-- Latency -->
            <div class="p-6 rounded-2xl glass shadow-lg space-y-4">
                <div class="flex justify-between items-center text-gray-400">
                    <span class="text-sm font-medium">Avg Latency</span>
                    <span class="text-xl">⚡</span>
                </div>
                <div class="flex items-baseline gap-2">
                    <span class="text-4xl font-bold">{{ "%.2f"|format(run.avg_latency) }}s</span>
                    {% if baseline %}
                        {% set delta = run.avg_latency - baseline.avg_latency %}
                        {% if delta < 0 %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-full">{{ "%.2f"|format(delta) }}s</span>
                        {% elif delta > 0 %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-red-500/10 text-red-400 rounded-full">+{{ "%.2f"|format(delta) }}s</span>
                        {% else %}
                            <span class="text-xs font-semibold px-2 py-0.5 bg-gray-500/10 text-gray-400 rounded-full">0.00s</span>
                        {% endif %}
                    {% endif %}
                </div>
                <p class="text-xs text-gray-500">Baseline latency: {{ "%.2f"|format(baseline.avg_latency) if baseline else 'N/A' }}s</p>
            </div>

            <!-- Token Cost -->
            <div class="p-6 rounded-2xl glass shadow-lg space-y-4">
                <div class="flex justify-between items-center text-gray-400">
                    <span class="text-sm font-medium">Token Cost</span>
                    <span class="text-xl">💵</span>
                </div>
                <div class="flex items-baseline gap-2">
                    <span class="text-4xl font-bold">${{ "%.4f"|format(run.total_cost) }}</span>
                    <span class="text-xs font-semibold px-2 py-0.5 bg-accentViolet/10 text-accentViolet rounded-full">{{ run.total_tokens }} tkn</span>
                </div>
                <p class="text-xs text-gray-500">Est. cost for {{ run.total_cases }} cases</p>
            </div>
        </section>

        <!-- VISUAL TREND CHART & METRIC SUMMARY -->
        <section class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 p-6 rounded-2xl glass shadow-lg space-y-4">
                <h3 class="text-lg font-semibold text-white">Historical Performance Trend</h3>
                <div class="h-64 relative">
                    <canvas id="trendChart"></canvas>
                </div>
            </div>
            
            <div class="p-6 rounded-2xl glass shadow-lg flex flex-col justify-between">
                <div class="space-y-4">
                    <h3 class="text-lg font-semibold text-white">Run Breakdown</h3>
                    <div class="divide-y divide-gray-800">
                        <div class="flex justify-between py-2.5 text-sm">
                            <span class="text-gray-400">Total Scored Cases</span>
                            <span class="font-medium text-white">{{ run.total_cases }}</span>
                        </div>
                        <div class="flex justify-between py-2.5 text-sm">
                            <span class="text-gray-400">Regressions Detected</span>
                            <span class="font-semibold {% if diff.regressions|length > 0 %}text-red-400{% else %}text-white{% endif %}">{{ diff.regressions|length }}</span>
                        </div>
                        <div class="flex justify-between py-2.5 text-sm">
                            <span class="text-gray-400">Improvements</span>
                            <span class="font-semibold {% if diff.improvements|length > 0 %}text-emerald-400{% else %}text-white{% endif %}">{{ diff.improvements|length }}</span>
                        </div>
                        <div class="flex justify-between py-2.5 text-sm">
                            <span class="text-gray-400">Stable Passed</span>
                            <span class="font-medium text-emerald-500">{{ diff.stable_pass|length }}</span>
                        </div>
                        <div class="flex justify-between py-2.5 text-sm">
                            <span class="text-gray-400">Stable Failed</span>
                            <span class="font-medium text-red-500/80">{{ diff.stable_fail|length }}</span>
                        </div>
                    </div>
                </div>
                
                <div class="pt-4 border-t border-gray-800">
                    <div class="bg-darkBg/60 border border-gray-800/80 rounded-xl p-3 text-xs text-gray-500">
                        <span class="font-semibold text-gray-400">Config Hash:</span>
                        <div class="font-mono mt-0.5 truncate">{{ run.config_hash }}</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- REGRESSED CASES -->
        {% if diff.regressions %}
        <section class="space-y-4">
            <h2 class="text-xl font-bold text-red-400 flex items-center gap-2">
                <span>🔴</span> Regressions Detected ({{ diff.regressions|length }})
            </h2>
            <div class="rounded-2xl glass shadow-lg overflow-hidden border border-red-500/20">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-red-500/5 text-xs text-red-300 font-semibold border-b border-gray-800">
                                <th class="p-4 w-24">Case ID</th>
                                <th class="p-4 w-1/3">Input Email</th>
                                <th class="p-4">Baseline Output</th>
                                <th class="p-4 bg-red-500/10">Current Output (Regressed)</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800 text-sm">
                            {% for reg in diff.regressions %}
                            <tr class="hover:bg-red-500/5 transition-colors">
                                <td class="p-4 font-mono font-semibold text-gray-400">{{ reg.case_id }}</td>
                                <td class="p-4 text-gray-300">
                                    <div class="line-clamp-3 hover:line-clamp-none max-w-md transition-all">{{ reg.input_text }}</div>
                                </td>
                                <td class="p-4 space-y-1">
                                    <span class="inline-block px-2 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20">
                                        {{ reg.baseline.category }}
                                    </span>
                                    <p class="text-xs text-gray-400 italic">"{{ reg.baseline.summary }}"</p>
                                    <p class="text-[10px] text-gray-500">Relevance: {{ reg.baseline.relevance_score }}/5</p>
                                </td>
                                <td class="p-4 bg-red-500/5 space-y-1">
                                    <span class="inline-block px-2 py-0.5 text-xs font-medium bg-red-500/10 text-red-400 rounded-full border border-red-500/20">
                                        {{ reg.current.category }}
                                    </span>
                                    <p class="text-xs text-gray-300 italic">"{{ reg.current.summary }}"</p>
                                    <p class="text-[10px] text-red-400/70">Relevance: {{ reg.current.relevance_score }}/5</p>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
        {% endif %}

        <!-- IMPROVED CASES -->
        {% if diff.improvements %}
        <section class="space-y-4">
            <h2 class="text-xl font-bold text-emerald-400 flex items-center gap-2">
                <span>🟢</span> Improvements ({{ diff.improvements|length }})
            </h2>
            <div class="rounded-2xl glass shadow-lg overflow-hidden border border-emerald-500/20">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-emerald-500/5 text-xs text-emerald-300 font-semibold border-b border-gray-800">
                                <th class="p-4 w-24">Case ID</th>
                                <th class="p-4 w-1/3">Input Email</th>
                                <th class="p-4">Baseline Output</th>
                                <th class="p-4 bg-emerald-500/10">Current Output (Improved)</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800 text-sm">
                            {% for imp in diff.improvements %}
                            <tr class="hover:bg-emerald-500/5 transition-colors">
                                <td class="p-4 font-mono font-semibold text-gray-400">{{ imp.case_id }}</td>
                                <td class="p-4 text-gray-300">
                                    <div class="line-clamp-3 hover:line-clamp-none max-w-md transition-all">{{ imp.input_text }}</div>
                                </td>
                                <td class="p-4 space-y-1">
                                    <span class="inline-block px-2 py-0.5 text-xs font-medium bg-red-500/10 text-red-400 rounded-full border border-red-500/20">
                                        {{ imp.baseline.category }}
                                    </span>
                                    <p class="text-xs text-gray-400 italic">"{{ imp.baseline.summary }}"</p>
                                    <p class="text-[10px] text-gray-500">Relevance: {{ imp.baseline.relevance_score }}/5</p>
                                </td>
                                <td class="p-4 bg-emerald-500/5 space-y-1">
                                    <span class="inline-block px-2 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20">
                                        {{ imp.current.category }}
                                    </span>
                                    <p class="text-xs text-gray-300 italic">"{{ imp.current.summary }}"</p>
                                    <p class="text-[10px] text-emerald-400/80">Relevance: {{ imp.current.relevance_score }}/5</p>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
        {% endif %}

        <!-- ALL TEST CASES (COLLAPSIBLE GRID) -->
        <section class="space-y-4">
            <div class="flex justify-between items-center">
                <h2 class="text-xl font-bold text-white">All Test Cases ({{ results|length }})</h2>
                <button onclick="document.getElementById('fullTable').classList.toggle('hidden')" class="px-4 py-1.5 bg-gray-800 hover:bg-gray-750 border border-gray-700/80 rounded-xl text-xs font-semibold text-gray-300 transition-colors">
                    Toggle Detailed Log
                </button>
            </div>
            
            <div id="fullTable" class="rounded-2xl glass shadow-lg overflow-hidden hidden border border-gray-800">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-gray-800/40 text-xs text-gray-400 font-semibold border-b border-gray-800">
                                <th class="p-4 w-24">Case ID</th>
                                <th class="p-4">Expected</th>
                                <th class="p-4">Actual Predictions</th>
                                <th class="p-4">Scores</th>
                                <th class="p-4 w-12">Latency</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-800 text-sm">
                            {% for r in results %}
                            <tr class="hover:bg-gray-800/20 transition-colors">
                                <td class="p-4 font-mono font-semibold text-gray-500">{{ r.case_id }}</td>
                                <td class="p-4 space-y-1 max-w-xs">
                                    <span class="inline-block px-2 py-0.5 text-xs font-semibold bg-gray-800 text-gray-400 rounded-full border border-gray-700/50">
                                        {{ r.expected_category }}
                                    </span>
                                    <p class="text-xs text-gray-400 italic truncate max-w-xs hover:text-clip hover:whitespace-normal" title="{{ r.expected_summary }}">"{{ r.expected_summary }}"</p>
                                </td>
                                <td class="p-4 space-y-1 max-w-xs">
                                    <span class="inline-block px-2 py-0.5 text-xs font-semibold {% if r.category_passed %}bg-emerald-500/10 text-emerald-400 border border-emerald-500/20{% else %}bg-red-500/10 text-red-400 border border-red-500/20{% endif %} rounded-full">
                                        {{ r.actual_category }}
                                    </span>
                                    <p class="text-xs text-gray-300 italic truncate max-w-xs hover:text-clip hover:whitespace-normal" title="{{ r.actual_summary }}">"{{ r.actual_summary }}"</p>
                                </td>
                                <td class="p-4 space-y-1">
                                    <div class="flex items-center gap-1.5">
                                        <span class="text-xs text-gray-400">Category:</span>
                                        <span class="font-semibold text-xs {% if r.category_passed %}text-emerald-400{% else %}text-red-400{% endif %}">
                                            {% if r.category_passed %}PASS{% else %}FAIL{% endif %}
                                        </span>
                                    </div>
                                    <div class="flex items-center gap-1.5">
                                        <span class="text-xs text-gray-400">Relevance:</span>
                                        <span class="font-semibold text-xs {% if r.relevance_score >= 3.5 %}text-emerald-400{% else %}text-yellow-400{% endif %}">
                                            {{ r.relevance_score }}/5
                                        </span>
                                    </div>
                                </td>
                                <td class="p-4 font-mono text-xs text-gray-400">{{ "%.2f"|format(r.latency) }}s</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
        
    </div>

    <!-- SCRIPT FOR HISTORICAL TREND CHART -->
    <script>
        const ctx = document.getElementById('trendChart').getContext('2d');
        const historyData = {{ history_json | safe }};
        
        // Reverse history to show chronological order (left to right)
        historyData.reverse();
        
        const labels = historyData.map(run => {
            const date = new Date(run.timestamp);
            return 'v' + run.prompt_version + ' (' + date.toLocaleDateString(undefined, {month: 'short', day: 'numeric'}) + ')';
        });
        const accuracyData = historyData.map(run => run.pass_rate);
        const relevanceData = historyData.map(run => run.avg_relevance * 20); // Normalized to 100% scale
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Category Accuracy (%)',
                        data: accuracyData,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        borderWidth: 2,
                        tension: 0.25,
                        fill: true
                    },
                    {
                        label: 'Relevance score normalized (x20 %)',
                        data: relevanceData,
                        borderColor: '#10b981',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        tension: 0.25
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#9ca3af',
                            font: { family: 'Plus Jakarta Sans', size: 11 }
                        }
                    }
                },
                scales: {
                    y: {
                        min: 0,
                        max: 100,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#9ca3af',
                            font: { family: 'Plus Jakarta Sans' }
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#9ca3af',
                            font: { family: 'Plus Jakarta Sans' }
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

def generate_report(
    run: EvalRun, 
    results: List[TestResult], 
    diff: Dict[str, Any], 
    status: str,
    drift: Optional[Dict[str, Any]] = None,
    baseline: Optional[EvalRun] = None
) -> str:
    """
    Renders the metrics and logs into a single HTML report file.
    Saves it in reports/ and returns the absolute file path.
    """
    history = get_run_history(limit=15)
    
    # Serialize historical runs for the Chart.js line plot
    history_serializable = []
    for h in history:
        history_serializable.append({
            "id": h.id,
            "timestamp": h.timestamp,
            "prompt_version": h.prompt_version,
            "pass_rate": h.pass_rate,
            "avg_relevance": h.avg_relevance
        })
        
    t = Template(HTML_TEMPLATE)
    rendered = t.render(
        run=run,
        results=results,
        diff=diff,
        status=status,
        drift=drift,
        baseline=baseline,
        history_json=json.dumps(history_serializable)
    )
    
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    report_file = os.path.join(reports_dir, f"report_{run.id}.html")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(rendered)
        
    # Also write a static symlink-like index.html file that points to the latest report
    latest_file = os.path.join(reports_dir, "latest.html")
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(rendered)
        
    return os.path.abspath(report_file)
