// Global references to Chart.js instances to allow clean updates
let bellChartInstance = null;
let entanglementChartInstance = null;
let teleportationChartInstance = null;

document.addEventListener("DOMContentLoaded", function () {
    // 1. Setup Tab Switching
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabs = document.querySelectorAll(".tab-content");
    const pageTitle = document.getElementById("page-title");

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });

    window.switchTab = function (tabId) {
        navButtons.forEach(btn => {
            if (btn.getAttribute("data-tab") === tabId) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        tabs.forEach(tab => {
            if (tab.id === `tab-${tabId}`) {
                tab.classList.add("active");
            } else {
                tab.classList.remove("active");
            }
        });

        // Update Title
        const titles = {
            home: "Home Overview",
            bell: "1. Bell States Laboratory",
            entanglement: "2. Quantum Entanglement Labs",
            teleportation: "3. Quantum Teleportation Protocol"
        };
        pageTitle.textContent = titles[tabId] || "Quantum Labs";

        // Auto-run simulations on tab enter if they haven't been simulated yet
        if (tabId === "bell" && !bellChartInstance) {
            runBellSimulation();
        } else if (tabId === "entanglement" && !entanglementChartInstance) {
            runEntanglementSimulation();
        } else if (tabId === "teleportation" && !teleportationChartInstance) {
            runTeleportationSimulation();
        }
    };

    // 2. Setup Slider Value Displays
    setupSliderDisplay("bell-shots-slider", "bell-shots-val");
    setupSliderDisplay("entanglement-shots-slider", "entanglement-shots-val");
    setupSliderDisplay("teleportation-shots-slider", "teleportation-shots-val");

    // Teleportation theta slider manual update
    const thetaSlider = document.getElementById("teleportation-theta-slider");
    const thetaBadge = document.getElementById("teleportation-badge");
    thetaSlider.addEventListener("input", function () {
        const val = parseFloat(this.value);
        thetaBadge.textContent = `θ = ${val.toFixed(2)} rad`;
        updateTheoreticalStateDisplay(val);
        // Clear active preset buttons if slider is moved manually
        document.querySelectorAll(".preset-btn").forEach(btn => {
            if (Math.abs(parseFloat(btn.getAttribute("data-theta")) - val) > 0.01) {
                btn.classList.remove("active");
            } else {
                btn.classList.add("active");
            }
        });
    });

    // 3. Teleportation Presets binding
    const presetBtns = document.querySelectorAll(".preset-btn");
    presetBtns.forEach(btn => {
        btn.addEventListener("click", function () {
            presetBtns.forEach(b => b.classList.remove("active"));
            this.classList.add("active");
            const theta = parseFloat(this.getAttribute("data-theta"));
            thetaSlider.value = theta;
            thetaBadge.textContent = `θ = ${theta.toFixed(2)} rad`;
            updateTheoreticalStateDisplay(theta);
            // Run automatically
            runTeleportationSimulation();
        });
    });

    // 4. Setup Simulation Run Buttons
    document.getElementById("run-bell-btn").addEventListener("click", runBellSimulation);
    document.getElementById("run-entanglement-btn").addEventListener("click", runEntanglementSimulation);
    document.getElementById("run-teleportation-btn").addEventListener("click", runTeleportationSimulation);

    // Initial state display for teleportation
    updateTheoreticalStateDisplay(0.0);
});

// Helper for slider displays
function setupSliderDisplay(sliderId, displayId) {
    const slider = document.getElementById(sliderId);
    const display = document.getElementById(displayId);
    if (slider && display) {
        slider.addEventListener("input", function () {
            display.textContent = this.value;
        });
    }
}

// Global theme options for charts - tuned for clean light theme
const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false }
    },
    scales: {
        y: {
            grid: { color: "#e2e8f0" },
            ticks: { color: "#475569", font: { family: "Inter", size: 11 } },
            beginAtZero: true
        },
        x: {
            grid: { display: false },
            ticks: { color: "#0f172a", font: { family: "Fira Code", size: 12, weight: "bold" } }
        }
    }
};

// Simulation: BELL STATES
function runBellSimulation() {
    const stateType = document.getElementById("bell-state-select").value;
    const shots = document.getElementById("bell-shots-slider").value;
    const btn = document.getElementById("run-bell-btn");
    
    setButtonLoading(btn, true);

    fetch(`/api/simulate/bell?state_type=${stateType}&shots=${shots}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                // Update badge
                const badgeText = {
                    phi_plus: "Perfect Match",
                    phi_minus: "Phase Match",
                    psi_plus: "Perfect Opposite",
                    psi_minus: "Phase Opposite"
                }[stateType];
                document.getElementById("bell-state-badge").textContent = badgeText;

                // Update circuit
                updateCircuitImage("bell-circuit-img-container", data.circuit_b64);

                // Update raw counts
                document.getElementById("bell-raw-counts").textContent = JSON.stringify(data.counts, null, 4);

                // Render Chart
                renderBellChart(data.counts, shots);
            }
        })
        .catch(err => console.error("Error running Bell state simulation:", err))
        .finally(() => setButtonLoading(btn, false));
}

function renderBellChart(counts, totalShots) {
    const ctx = document.getElementById("bell-chart").getContext("2d");
    
    // Sort all possible 2-qubit states for consistent labels
    const labels = ["00", "01", "10", "11"];
    const dataValues = labels.map(l => counts[l] || 0);
    const percentages = dataValues.map(v => ((v / totalShots) * 100).toFixed(1));

    if (bellChartInstance) {
        bellChartInstance.destroy();
    }

    bellChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels.map((l, i) => `${l} (${percentages[i]}%)`),
            datasets: [{
                data: dataValues,
                backgroundColor: "rgba(79, 70, 229, 0.2)", // Soft indigo fill
                borderColor: "#4f46e5",                   // Slate indigo border
                borderWidth: 2,
                borderRadius: 4
            }]
        },
        options: {
            ...chartOptions,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return ` ${context.parsed.y} runs (${percentages[context.dataIndex]}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Simulation: ENTANGLEMENT
function runEntanglementSimulation() {
    const aliceBasis = document.getElementById("alice-basis-select").value;
    const bobBasis = document.getElementById("bob-basis-select").value;
    const shots = document.getElementById("entanglement-shots-slider").value;
    const btn = document.getElementById("run-entanglement-btn");

    setButtonLoading(btn, true);

    fetch(`/api/simulate/entanglement?alice_basis=${aliceBasis}&bob_basis=${bobBasis}&shots=${shots}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                // Update badge
                document.getElementById("entanglement-basis-badge").textContent = `${aliceBasis} - ${bobBasis} Bases`;

                // Update circuit
                updateCircuitImage("entanglement-circuit-img-container", data.circuit_b64);

                // Analyze correlation
                updateEntanglementAnalysis(data.counts, aliceBasis, bobBasis, shots);

                // Render Chart
                renderEntanglementChart(data.counts, shots);
            }
        })
        .catch(err => console.error("Error running Entanglement simulation:", err))
        .finally(() => setButtonLoading(btn, false));
}

function renderEntanglementChart(counts, totalShots) {
    const ctx = document.getElementById("entanglement-chart").getContext("2d");
    const labels = ["00", "01", "10", "11"];
    const dataValues = labels.map(l => counts[l] || 0);
    const percentages = dataValues.map(v => ((v / totalShots) * 100).toFixed(1));

    if (entanglementChartInstance) {
        entanglementChartInstance.destroy();
    }

    entanglementChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels.map((l, i) => `${l} (${percentages[i]}%)`),
            datasets: [{
                data: dataValues,
                backgroundColor: "rgba(13, 148, 136, 0.2)", // Soft teal fill
                borderColor: "#0d9488",                   // Teal border
                borderWidth: 2,
                borderRadius: 4
            }]
        },
        options: {
            ...chartOptions,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return ` ${context.parsed.y} runs (${percentages[context.dataIndex]}%)`;
                        }
                    }
                }
            }
        }
    });
}

function updateEntanglementAnalysis(counts, aliceBasis, bobBasis, totalShots) {
    const analysisBox = document.getElementById("entanglement-analysis").querySelector(".analysis-box");
    
    const count00 = counts["00"] || 0;
    const count11 = counts["11"] || 0;
    const count01 = counts["01"] || 0;
    const count10 = counts["10"] || 0;
    
    const correlationPercent = (((count00 + count11) / totalShots) * 100).toFixed(1);
    const antiCorrelationPercent = (((count01 + count10) / totalShots) * 100).toFixed(1);

    if (aliceBasis === bobBasis) {
        analysisBox.className = "analysis-box correlated";
        analysisBox.innerHTML = `
            <strong><i class="fa-solid fa-circle-check"></i> Connected Outcomes (${correlationPercent}% matches)</strong><br>
            Alice and Bob measured their qubits in matching directions (<strong>${aliceBasis}-basis</strong>). 
            Even though the individual results are completely random, their results 
            <strong>matched</strong> (yielding either 00 or 11). This demonstrates quantum correlation in action!
        `;
    } else {
        analysisBox.className = "analysis-box uncorrelated";
        analysisBox.innerHTML = `
            <strong><i class="fa-solid fa-circle-xmark"></i> Uncorrelated Outcomes (${correlationPercent}% match, ${antiCorrelationPercent}% opposite)</strong><br>
            Alice and Bob measured in different directions (<strong>Alice in ${aliceBasis}, Bob in ${bobBasis}</strong>). 
            Due to quantum complementarity, measuring in different bases destroys the correlation, leaving a random 25% spread across all outcomes.
        `;
    }
}

// Simulation: QUANTUM TELEPORTATION
function runTeleportationSimulation() {
    const theta = document.getElementById("teleportation-theta-slider").value;
    const shots = document.getElementById("teleportation-shots-slider").value;
    const btn = document.getElementById("run-teleportation-btn");

    setButtonLoading(btn, true);

    fetch(`/api/simulate/teleportation?theta=${theta}&shots=${shots}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                // Update badge
                document.getElementById("teleportation-badge").textContent = `θ = ${parseFloat(theta).toFixed(2)} rad`;

                // Update circuit
                updateCircuitImage("teleportation-circuit-img-container", data.circuit_b64);

                // Verify Bob's reconstructed qubit (Bit 2 - leftmost character in results)
                verifyBobQubit(data.counts, shots);

                // Render Chart
                renderTeleportationChart(data.counts, shots);
            }
        })
        .catch(err => console.error("Error running Teleportation simulation:", err))
        .finally(() => setButtonLoading(btn, false));
}

function updateTheoreticalStateDisplay(theta) {
    const coeff0 = Math.cos(theta / 2);
    const coeff1 = Math.sin(theta / 2);
    const prob0 = coeff0 * coeff0;
    const prob1 = coeff1 * coeff1;

    document.getElementById("theory-coeff-0").textContent = coeff0.toFixed(4);
    document.getElementById("theory-coeff-1").textContent = coeff1.toFixed(4);
    
    document.getElementById("theory-bar-0").style.width = `${prob0 * 100}%`;
    document.getElementById("theory-bar-1").style.width = `${prob1 * 100}%`;
    
    document.getElementById("theory-pct-0").textContent = `${Math.round(prob0 * 100)}%`;
    document.getElementById("theory-pct-1").textContent = `${Math.round(prob1 * 100)}%`;
}

// Qiskit keys are c2 c1 c0. c2 is Bob's qubit.
function verifyBobQubit(counts, totalShots) {
    let bobZeroCounts = 0;
    let bobOneCounts = 0;

    for (let state in counts) {
        if (state.startsWith("0")) {
            bobZeroCounts += counts[state];
        } else if (state.startsWith("1")) {
            bobOneCounts += counts[state];
        }
    }

    const prob0 = bobZeroCounts / totalShots;
    const prob1 = bobOneCounts / totalShots;

    const coeff0 = Math.sqrt(prob0);
    const coeff1 = Math.sqrt(prob1);

    document.getElementById("measured-coeff-0").textContent = coeff0.toFixed(4);
    document.getElementById("measured-coeff-1").textContent = coeff1.toFixed(4);

    document.getElementById("measured-bar-0").style.width = `${prob0 * 100}%`;
    document.getElementById("measured-bar-1").style.width = `${prob1 * 100}%`;

    document.getElementById("measured-pct-0").textContent = `${Math.round(prob0 * 100)}%`;
    document.getElementById("measured-pct-1").textContent = `${Math.round(prob1 * 100)}%`;
}

function renderTeleportationChart(counts, totalShots) {
    const ctx = document.getElementById("teleportation-chart").getContext("2d");
    
    // 3 Qubits -> 8 states: 000, 001, 010, 011, 100, 101, 110, 111
    const labels = ["000", "001", "010", "011", "100", "101", "110", "111"];
    const dataValues = labels.map(l => counts[l] || 0);
    const percentages = dataValues.map(v => ((v / totalShots) * 100).toFixed(1));

    if (teleportationChartInstance) {
        teleportationChartInstance.destroy();
    }

    // Softer colors: indigo for Bob = 0, violet for Bob = 1
    const backgroundColors = labels.map(l => l.startsWith("0") ? "rgba(79, 70, 229, 0.2)" : "rgba(124, 58, 237, 0.2)");
    const borderColors = labels.map(l => l.startsWith("0") ? "#4f46e5" : "#7c3aed");

    teleportationChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels.map((l, i) => `${l} (${percentages[i]}%)`),
            datasets: [{
                data: dataValues,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 2,
                borderRadius: 4
            }]
        },
        options: {
            ...chartOptions,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return ` ${context.parsed.y} runs (${percentages[context.dataIndex]}%)`;
                        }
                    }
                }
            }
        }
    });
}


// Shared helper: UI updates
function setButtonLoading(button, isLoading) {
    if (isLoading) {
        button.classList.add("loading");
        button.disabled = true;
    } else {
        button.classList.remove("loading");
        button.disabled = false;
    }
}

function updateCircuitImage(containerId, base64Str) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (base64Str) {
        container.innerHTML = `<img src="data:image/png;base64,${base64Str}" alt="Quantum Circuit Diagram">`;
    } else {
        container.innerHTML = `<p class="text-danger"><i class="fa-solid fa-triangle-exclamation"></i> Error rendering circuit diagram.</p>`;
    }
}