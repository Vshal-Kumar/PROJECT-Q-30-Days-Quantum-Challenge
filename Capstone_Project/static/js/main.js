document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const secretKeyInput = document.getElementById('secret-key');
    const btnGenerateKey = document.getElementById('btn-generate-key');
    const btnRegister = document.getElementById('btn-register');
    const noiseSlider = document.getElementById('noise-rate');
    const noiseDisplay = document.getElementById('noise-display');
    const eprSizeInput = document.getElementById('epr-size');
    const bb84SizeInput = document.getElementById('bb84-size');
    const btnClearTerminal = document.getElementById('btn-clear-terminal');
    const terminalBody = document.getElementById('terminal-body');
    const btnRunNormal = document.getElementById('btn-run-normal');
    const btnRuns = document.querySelectorAll('.btn-run');
    const btnRunBenchmark = document.getElementById('btn-run-benchmark');
    
    // Telemetry Elements
    const authStatus = document.getElementById('auth-status');
    const encryptionBadge = document.getElementById('encryption-badge');
    const metricAuthQber = document.getElementById('metric-auth-qber');
    const metricBb84Qber = document.getElementById('metric-bb84-qber');
    const barAuthQber = document.getElementById('bar-auth-qber');
    const barBb84Qber = document.getElementById('bar-bb84-qber');
    const metricLatency = document.getElementById('metric-latency');
    const metricGates = document.getElementById('metric-gates');
    const metricDepth = document.getElementById('metric-depth');
    
    // Plots and Table Elements
    const plotQberNoise = document.getElementById('plot-qber-noise');
    const plotDetectionBatch = document.getElementById('plot-detection-batch');
    const benchmarkTableBody = document.querySelector('#benchmark-table tbody');

    // Update noise slider value display
    noiseSlider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        noiseDisplay.textContent = (val * 100).toFixed(1) + '%';
    });

    // Helper: Clear Terminal
    const clearTerminal = () => {
        terminalBody.innerHTML = '';
    };
    btnClearTerminal.addEventListener('click', clearTerminal);

    // Helper: Write Line to Terminal
    const writeTerminalLine = (text, className = 'normal-line') => {
        const line = document.createElement('div');
        line.className = `terminal-line ${className}`;
        line.textContent = text;
        terminalBody.appendChild(line);
        terminalBody.scrollTop = terminalBody.scrollHeight;
    };

    // Helper: Determine log line color class
    const getLogClass = (line) => {
        if (line.includes('===')) return 'system-line';
        if (line.includes('Phase 1')) return 'auth-phase-line';
        if (line.includes('Phase 2')) return 'bb84-phase-line';
        if (line.includes('Phase 3')) return 'crypto-phase-line';
        if (line.includes('SUCCESSFUL') || line.includes('VALIDATED') || line.includes('correlation')) return 'success-line';
        if (line.includes('FAILED') || line.includes('terminated') || line.includes('aborts')) return 'error-line';
        return 'normal-line';
    };

    // Helper: Animate lines writing with typewriter delay
    const writeLogsSequentially = async (logs) => {
        for (const log of logs) {
            const lineClass = getLogClass(log);
            writeTerminalLine(log, lineClass);
            // Dynamic delay depending on line complexity
            await new Promise(resolve => setTimeout(resolve, log.length * 1.5 + 40));
        }
    };

    // Auto-generate random key
    btnGenerateKey.addEventListener('click', () => {
        const chars = 'abcdef0123456789';
        let key = '';
        for (let i = 0; i < 32; i++) {
            key += chars[Math.floor(Math.random() * chars.length)];
        }
        secretKeyInput.value = key;
        writeTerminalLine(`[SYSTEM] Client generated random pre-shared secret key: ${key}`);
    });

    // Register Secret Key
    btnRegister.addEventListener('click', async () => {
        const secret = secretKeyInput.value.trim();
        writeTerminalLine(`[SYSTEM] Registering pre-shared secret key with Bob (server)...`);
        
        try {
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ secret: secret })
            });
            const data = await res.json();
            
            if (data.success) {
                secretKeyInput.value = data.secret;
                writeTerminalLine(`[SUCCESS] Key successfully registered! active secret: ${data.secret}`, 'success-line');
            }
        } catch (err) {
            writeTerminalLine(`[ERROR] Failed to register key: ${err.message}`, 'error-line');
        }
    });

    // Trigger Simulation Run
    btnRuns.forEach(button => {
        button.addEventListener('click', async (e) => {
            // Disable all run buttons during execution
            btnRuns.forEach(b => b.disabled = true);
            btnRunBenchmark.disabled = true;
            
            const scenario = button.getAttribute('data-scenario');
            const noise = parseFloat(noiseSlider.value);
            const eprSize = parseInt(eprSizeInput.value) || 100;
            const bb84Size = parseInt(bb84SizeInput.value) || 100;

            clearTerminal();
            writeTerminalLine(`[SYSTEM] Connecting to quantum simulator...`);
            writeTerminalLine(`[SYSTEM] Requesting scenario: ${scenario === 'none' ? 'Normal Handshake' : scenario}...`);

            // Reset Telemetry Display
            authStatus.className = 'status-value status-standby';
            authStatus.textContent = 'EXECUTING';
            encryptionBadge.className = 'encryption-badge-inactive';
            metricAuthQber.textContent = '--';
            metricBb84Qber.textContent = '--';
            barAuthQber.style.width = '0%';
            barBb84Qber.style.width = '0%';
            metricLatency.textContent = '--';
            metricGates.textContent = '--';
            metricDepth.textContent = '--';

            try {
                const res = await fetch('/api/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        attack_type: scenario,
                        noise_rate: noise,
                        epr_size: eprSize,
                        bb84_size: bb84Size
                    })
                });
                
                const data = await res.json();
                
                // Write logs with animation
                await writeLogsSequentially(data.logs);

                // Update Telemetry Panel
                // Auth Status
                if (data.auth_success && data.bb84_success) {
                    authStatus.textContent = 'SECURELY AUTHENTICATED';
                    authStatus.className = 'status-value status-secure';
                    encryptionBadge.className = 'encryption-badge-active';
                } else {
                    authStatus.textContent = 'CONNECTION BREACHED';
                    authStatus.className = 'status-value status-breached';
                    encryptionBadge.className = 'encryption-badge-inactive';
                }

                // Auth QBER
                if (data.auth_qber !== null) {
                    const qberPct = (data.auth_qber * 100).toFixed(1) + '%';
                    metricAuthQber.textContent = qberPct;
                    barAuthQber.style.width = Math.min(100, data.auth_qber * 100 * 2) + '%'; // Scaled for display
                    if (data.auth_qber >= 0.15) {
                        barAuthQber.style.backgroundColor = 'var(--error-red)';
                    } else {
                        barAuthQber.style.backgroundColor = 'var(--success-green)';
                    }
                }

                // BB84 QBER
                if (data.bb84_qber !== null) {
                    const bb84Pct = (data.bb84_qber * 100).toFixed(1) + '%';
                    metricBb84Qber.textContent = bb84Pct;
                    barBb84Qber.style.width = Math.min(100, data.bb84_qber * 100 * 3.3) + '%'; // Scaled
                    if (data.bb84_qber >= 0.11) {
                        barBb84Qber.style.backgroundColor = 'var(--error-red)';
                    } else {
                        barBb84Qber.style.backgroundColor = 'var(--accent-blue)';
                    }
                } else {
                    metricBb84Qber.textContent = 'ABORTED';
                }

                // Latency and Gates
                metricLatency.textContent = data.latency_ms.toFixed(2) + ' ms';
                metricGates.textContent = data.gate_count;
                metricDepth.textContent = data.depth;

            } catch (err) {
                writeTerminalLine(`[SYSTEM ERROR] Simulation request failed: ${err.message}`, 'error-line');
                authStatus.textContent = 'SIMULATION ERROR';
                authStatus.className = 'status-value status-breached';
            } finally {
                // Re-enable buttons
                btnRuns.forEach(b => b.disabled = false);
                btnRunBenchmark.disabled = false;
            }
        });
    });

    // Run Live Benchmarks & Regenerate Plots
    btnRunBenchmark.addEventListener('click', async () => {
        btnRunBenchmark.disabled = true;
        btnRuns.forEach(b => b.disabled = true);
        
        writeTerminalLine(`[SYSTEM] Starting live benchmark suite (10 iterations per scenario)...`);
        writeTerminalLine(`[SYSTEM] Running monte-carlo loops to evaluate QBER averages...`);
        
        try {
            const res = await fetch('/api/benchmarks');
            const data = await res.json();
            
            // Rebuild benchmark table
            benchmarkTableBody.innerHTML = '';
            for (const [scenario, metrics] of Object.entries(data)) {
                const tr = document.createElement('tr');
                
                const formatPct = (val) => val !== null ? (val * 100).toFixed(1) + '%' : 'N/A';
                
                tr.innerHTML = `
                    <td><strong>${scenario.toUpperCase()}</strong></td>
                    <td>${formatPct(metrics.auth_success_rate)}</td>
                    <td>${formatPct(metrics.avg_auth_qber)}</td>
                    <td>${metrics.bb84_success_rate !== null ? formatPct(metrics.bb84_success_rate) : 'N/A'}</td>
                    <td>${metrics.avg_bb84_qber > 0 ? (metrics.avg_bb84_qber * 100).toFixed(1) + '%' : 'N/A'}</td>
                    <td>${formatPct(metrics.key_derivation_rate)}</td>
                    <td>${metrics.avg_latency_ms.toFixed(2)} ms</td>
                `;
                benchmarkTableBody.appendChild(tr);
            }
            
            // Refresh plots with cache-busting parameter
            const timestamp = Date.now();
            plotQberNoise.src = `/static/diagrams/qber_vs_noise.png?t=${timestamp}`;
            plotDetectionBatch.src = `/static/diagrams/detection_vs_batch_size.png?t=${timestamp}`;
            
            writeTerminalLine(`[SUCCESS] Live statistical benchmarks completed! Charts regenerated successfully.`, 'success-line');
            
        } catch (err) {
            writeTerminalLine(`[ERROR] Benchmark run failed: ${err.message}`, 'error-line');
        } finally {
            btnRunBenchmark.disabled = false;
            btnRuns.forEach(b => b.disabled = false);
        }
    });
});
