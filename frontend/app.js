// API endpoint
const API_URL = 'http://localhost:5000';

// DOM elements
const youtubeLink = document.getElementById('youtubeLink');
const analyzeBtn = document.getElementById('analyzeBtn');
const btnText = document.getElementById('btnText');
const loadingIndicator = document.getElementById('loadingIndicator');
const progressSection = document.getElementById('progressSection');
const progressSteps = document.getElementById('progressSteps');
const toggleProgress = document.getElementById('toggleProgress');
const toggleText = document.getElementById('toggleText');
const toggleIcon = document.getElementById('toggleIcon');
const errorMessage = document.getElementById('errorMessage');
const errorText = document.getElementById('errorText');
const resetGraphBtn = document.getElementById('resetGraphBtn');
const graphSvg = document.getElementById('graph');

// Event listeners
analyzeBtn.addEventListener('click', analyzeVideo);
toggleProgress.addEventListener('click', toggleProgressVisibility);
resetGraphBtn.addEventListener('click', () => {
    if (window.currentGraphData) {
        renderGraph(window.currentGraphData);
        // Fit the graph to view after a short delay to let the simulation settle
        setTimeout(() => {
            if (window.zoomToFit) {
                window.zoomToFit();
            }
        }, 500);
    }
});

// Allow Enter key to trigger analysis
youtubeLink.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        analyzeVideo();
    }
});

// Smooth scroll for navigation
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

function toggleProgressVisibility() {
    const isHidden = progressSteps.classList.contains('hidden');
    
    if (isHidden) {
        progressSteps.classList.remove('hidden');
        toggleText.textContent = 'Hide Processing Updates';
        toggleIcon.classList.remove('rotate-180');
    } else {
        progressSteps.classList.add('hidden');
        toggleText.textContent = 'Show Processing Updates';
        toggleIcon.classList.add('rotate-180');
    }
}

function addProgressStep(message, type = 'info') {
    const step = document.createElement('div');
    step.className = 'stream-line text-gray-700';
    
    let prefix = '';
    if (type === 'success') {
        prefix = '✓';
        step.classList.add('text-green-600');
    } else if (type === 'error') {
        prefix = '✗';
        step.classList.add('text-red-600');
    } else if (type === 'warning') {
        prefix = '⚠';
        step.classList.add('text-yellow-600');
    } else {
        prefix = '→';
    }
    
    step.textContent = `${prefix} ${message}`;
    progressSteps.appendChild(step);
    progressSteps.scrollTop = progressSteps.scrollHeight;
}

function clearProgressSteps() {
    progressSteps.innerHTML = '';
}

async function analyzeVideo() {
    const link = youtubeLink.value.trim();
    
    if (!link) {
        showError('Please enter a YouTube link');
        return;
    }
    
    // Validate YouTube URL
    if (!isValidYouTubeUrl(link)) {
        showError('Please enter a valid YouTube link');
        return;
    }
    
    // Show loading, hide error
    loadingIndicator.classList.remove('hidden');
    progressSection.classList.remove('hidden');
    progressSteps.classList.remove('hidden'); // Show progress steps automatically
    toggleText.textContent = 'Hide Processing Details';
    toggleIcon.classList.remove('rotate-180');
    errorMessage.classList.add('hidden');
    analyzeBtn.disabled = true;
    btnText.textContent = 'Analyzing...';
    resetGraphBtn.classList.add('hidden');
    clearProgressSteps();
    
    // Track if we used Whisper API
    let usedWhisperAPI = false;
    let transcriptLength = 0;
    
    try {
        // Send the POST data
        fetch(`${API_URL}/analyze-stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ youtube_url: link })
        }).then(response => {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            function readStream() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        loadingIndicator.classList.add('hidden');
                        analyzeBtn.disabled = false;
                        btnText.textContent = 'Analyze Video';
                        return;
                    }
                    
                    const text = decoder.decode(value);
                    const lines = text.split('\n');
                    
                    lines.forEach(line => {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.substring(6));
                                
                                if (data.type === 'progress') {
                                    addProgressStep(data.message, 'info');
                                    
                                    // Detect if Whisper API was used
                                    if (data.message.includes('Whisper API') || data.message.includes('Downloading audio')) {
                                        usedWhisperAPI = true;
                                    }
                                    
                                    // Extract transcript length if mentioned
                                    if (data.transcriptLength) {
                                        transcriptLength = data.transcriptLength;
                                    }
                                } else if (data.type === 'complete') {
                                    addProgressStep('Analysis completed successfully!', 'success');
                                    
                                    // Handle graph rendering or error
                                    if (data.graph) {
                                        renderGraph(data.graph);
                                        window.currentGraphData = data.graph;
                                        resetGraphBtn.classList.remove('hidden');
                                    } else if (data.graphError) {
                                        // Show graph error message but continue
                                        addProgressStep(`Graph generation failed: ${data.graphError}`, 'warning');
                                        // Clear graph area and show message
                                        d3.select('#graph').selectAll('*').remove();
                                        d3.select('#graph')
                                            .append('text')
                                            .attr('x', '50%')
                                            .attr('y', '50%')
                                            .attr('text-anchor', 'middle')
                                            .attr('fill', '#64748b')
                                            .style('font-size', '14px')
                                            .text('Graph generation failed. Transcript is still available below.');
                                        resetGraphBtn.classList.add('hidden');
                                    }
                                    
                                    loadingIndicator.classList.add('hidden');
                                    analyzeBtn.disabled = false;
                                    btnText.textContent = 'Analyze Video';
                                    
                                    // Scroll to results
                                    document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
                                } else if (data.type === 'error') {
                                    addProgressStep(data.message, 'error');
                                    showError(data.message);
                                    loadingIndicator.classList.add('hidden');
                                    analyzeBtn.disabled = false;
                                    btnText.textContent = 'Analyze Video';
                                }
                            } catch (e) {
                                console.error('Error parsing SSE data:', e);
                            }
                        }
                    });
                    
                    readStream();
                });
            }
            
            readStream();
        }).catch(error => {
            addProgressStep('Connection error: ' + error.message, 'error');
            showError(error.message);
            loadingIndicator.classList.add('hidden');
            analyzeBtn.disabled = false;
            btnText.textContent = 'Analyze Video';
        });
        
    } catch (error) {
        addProgressStep('Error: ' + error.message, 'error');
        showError(error.message);
        loadingIndicator.classList.add('hidden');
        analyzeBtn.disabled = false;
        btnText.textContent = 'Analyze Video';
    }
}

function isValidYouTubeUrl(url) {
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$/;
    return youtubeRegex.test(url);
}

function showError(message) {
    errorText.textContent = message;
    errorMessage.classList.remove('hidden');
}

function renderGraph(graphData) {
    // Clear previous graph
    d3.select('#graph').selectAll('*').remove();
    
    const width = document.getElementById('graphContainer').clientWidth;
    const height = 600;
    
    const svg = d3.select('#graph')
        .attr('width', width)
        .attr('height', height);
    
    // Create a group for zoom/pan
    const g = svg.append('g');
    
    // Add zoom behavior
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        })
        .filter(function(event) {
            // Allow zoom on wheel, but not on drag if over a node/link
            return event.type !== 'mousedown' || event.target === this;
        });
    
    svg.call(zoom);
    
    // Function to fit graph to view
    window.zoomToFit = function() {
        if (!graphData.nodes || graphData.nodes.length === 0) return;
        
        // Calculate bounds of all nodes
        const padding = 50;
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        graphData.nodes.forEach(node => {
            if (node.x < minX) minX = node.x;
            if (node.y < minY) minY = node.y;
            if (node.x > maxX) maxX = node.x;
            if (node.y > maxY) maxY = node.y;
        });
        
        const boundsWidth = maxX - minX;
        const boundsHeight = maxY - minY;
        
        // Calculate scale to fit
        const scale = Math.min(
            (width - padding * 2) / boundsWidth,
            (height - padding * 2) / boundsHeight,
            1 // Don't zoom in more than 100%
        );
        
        // Calculate translation to center
        const translateX = (width - boundsWidth * scale) / 2 - minX * scale;
        const translateY = (height - boundsHeight * scale) / 2 - minY * scale;
        
        // Apply transform with animation
        svg.transition()
            .duration(750)
            .call(
                zoom.transform,
                d3.zoomIdentity.translate(translateX, translateY).scale(scale)
            );
    };
    
    // Create tooltip div for custom tooltips
    let tooltip = d3.select('#graphContainer').select('.graph-tooltip');
    if (tooltip.empty()) {
        tooltip = d3.select('#graphContainer')
            .append('div')
            .attr('class', 'graph-tooltip')
            .style('position', 'absolute')
            .style('visibility', 'hidden')
            .style('background-color', 'rgba(0, 0, 0, 0.9)')
            .style('color', 'white')
            .style('padding', '12px')
            .style('border-radius', '8px')
            .style('font-size', '13px')
            .style('max-width', '300px')
            .style('pointer-events', 'none')
            .style('z-index', '1000')
            .style('box-shadow', '0 4px 6px rgba(0, 0, 0, 0.3)');
    }
    
    // Create force simulation
    const simulation = d3.forceSimulation(graphData.nodes)
        .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(120))
        .force('charge', d3.forceManyBody().strength(-400))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(35));
    
    // Create arrow markers for directed edges
    svg.append('defs').selectAll('marker')
        .data(['opinion', 'relation'])
        .enter().append('marker')
        .attr('id', d => d)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 30)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', '#9ca3af');
    
    // Create invisible wider links for easier hovering
    const linkHitArea = g.append('g')
        .selectAll('line')
        .data(graphData.links)
        .enter().append('line')
        .attr('stroke', 'transparent')
        .attr('stroke-width', 15)
        .style('cursor', 'pointer')
        .on('mouseover', function(event, d) {
            // Find the corresponding visible link and highlight it
            const index = graphData.links.indexOf(d);
            d3.select(link.nodes()[index])
                .attr('stroke-opacity', 1)
                .attr('stroke-width', 3.5);
            
            // Show link tooltip
            let linkText = `<strong>${d.label}</strong>`;
            if (d.label === 'expresses') {
                const targetNode = graphData.nodes.find(n => n.id === d.target.id || n.id === d.target);
                if (targetNode && targetNode.sentiment) {
                    const sentimentColor = targetNode.sentiment === 'positive' ? '#10b981' : 
                                          targetNode.sentiment === 'negative' ? '#ef4444' : '#9ca3af';
                    linkText += `<br/><span style="color: ${sentimentColor};">Sentiment: ${targetNode.sentiment}</span>`;
                }
            }
            
            tooltip.html(linkText)
                .style('visibility', 'visible');
        })
        .on('mousemove', function(event) {
            const containerRect = document.getElementById('graphContainer').getBoundingClientRect();
            tooltip
                .style('top', (event.clientY - containerRect.top + 15) + 'px')
                .style('left', (event.clientX - containerRect.left + 15) + 'px');
        })
        .on('mouseout', function(event, d) {
            const index = graphData.links.indexOf(d);
            d3.select(link.nodes()[index])
                .attr('stroke-opacity', 0.6)
                .attr('stroke-width', 2.5);
            tooltip.style('visibility', 'hidden');
        });
    
    // Create visible links
    const link = g.append('g')
        .selectAll('line')
        .data(graphData.links)
        .enter().append('line')
        .attr('stroke', d => {
            // For "expresses" links, get sentiment from the target opinion node
            if (d.label === 'expresses') {
                const targetNode = graphData.nodes.find(n => n.id === d.target.id || n.id === d.target);
                if (targetNode && targetNode.sentiment) {
                    if (targetNode.sentiment === 'positive') return '#10b981';
                    if (targetNode.sentiment === 'negative') return '#ef4444';
                }
            }
            return '#9ca3af';
        })
        .attr('stroke-width', 2.5)
        .attr('stroke-opacity', 0.6)
        .attr('marker-end', 'url(#opinion)')
        .style('pointer-events', 'none'); // Disable pointer events on visible links since hit area handles it
    
    // Create link labels
    const linkLabel = g.append('g')
        .selectAll('text')
        .data(graphData.links)
        .enter().append('text')
        .attr('font-size', 11)
        .attr('fill', '#6b7280')
        .attr('font-weight', '500')
        .text(d => d.label || '');
    
    // Create nodes
    const node = g.append('g')
        .selectAll('circle')
        .data(graphData.nodes)
        .enter().append('circle')
        .attr('r', d => d.type === 'speaker' ? 22 : 16)
        .attr('fill', d => {
            if (d.type === 'speaker') return '#3b82f6';
            if (d.type === 'topic') return '#a855f7';
            if (d.type === 'opinion') {
                if (d.sentiment === 'positive') return '#10b981';
                if (d.sentiment === 'negative') return '#ef4444';
                return '#9ca3af';
            }
            return '#6b7280';
        })
        .attr('stroke', '#fff')
        .attr('stroke-width', 3)
        .style('cursor', 'pointer')
        .on('mouseover', function(event, d) {
            // Show custom tooltip
            let tooltipText = `<strong>${d.label}</strong><br/>`;
            tooltipText += `<span style="color: #94a3b8;">Type: ${d.type}</span>`;
            
            if (d.sentiment) {
                const sentimentColor = d.sentiment === 'positive' ? '#10b981' : 
                                      d.sentiment === 'negative' ? '#ef4444' : '#9ca3af';
                tooltipText += `<br/><span style="color: ${sentimentColor};">Sentiment: ${d.sentiment}</span>`;
            }
            
            if (d.context) {
                tooltipText += `<br/><br/><span style="color: #e2e8f0;">${d.context}</span>`;
            }
            
            tooltip.html(tooltipText)
                .style('visibility', 'visible');
        })
        .on('mousemove', function(event) {
            const containerRect = document.getElementById('graphContainer').getBoundingClientRect();
            tooltip
                .style('top', (event.clientY - containerRect.top + 15) + 'px')
                .style('left', (event.clientX - containerRect.left + 15) + 'px');
        })
        .on('mouseout', function() {
            tooltip.style('visibility', 'hidden');
        })
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));
    
    // Remove old basic tooltips (replaced by custom ones)
    // node.append('title')
    //     .text(d => `${d.label}\n(${d.type}${d.sentiment ? ', ' + d.sentiment : ''})`);
    
    // Add labels
    const label = g.append('g')
        .selectAll('text')
        .data(graphData.nodes)
        .enter().append('text')
        .text(d => d.label)
        .attr('font-size', 13)
        .attr('dx', 28)
        .attr('dy', 5)
        .attr('fill', '#1f2937')
        .attr('font-weight', d => d.type === 'speaker' ? '700' : '500')
        .style('pointer-events', 'none');
    
    // Update positions on each tick
    simulation.on('tick', () => {
        // Constrain nodes to stay within bounds with padding
        const padding = 50;
        graphData.nodes.forEach(node => {
            node.x = Math.max(padding, Math.min(width - padding, node.x));
            node.y = Math.max(padding, Math.min(height - padding, node.y));
        });
        
        linkHitArea
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        linkLabel
            .attr('x', d => (d.source.x + d.target.x) / 2)
            .attr('y', d => (d.source.y + d.target.y) / 2);
        
        node
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);
        
        label
            .attr('x', d => d.x)
            .attr('y', d => d.y);
    });
    
    // Auto-fit graph to view after simulation settles
    simulation.on('end', () => {
        setTimeout(() => {
            if (window.zoomToFit) {
                window.zoomToFit();
            }
        }, 100);
    });
    
    // Drag functions
    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    
    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    
    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
}
