
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const resultsGrid = document.getElementById('results-grid');
    const categoryLinks = document.querySelectorAll('.category-link');

    let currentCategory = 'all';
    let searchTimeout;

    // --- Event Listeners ---
    searchInput.addEventListener('keyup', () => {
        clearTimeout(searchTimeout);
        // Debounce the search to avoid excessive API calls
        searchTimeout = setTimeout(() => {
            performSearch(searchInput.value, currentCategory);
        }, 300);
    });

    categoryLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            currentCategory = link.dataset.category;

            // Update active link style
            categoryLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');

            performSearch(searchInput.value, currentCategory);
        });
    });

    // --- API Call ---
    async function performSearch(query, category) {
        // Only search if the query is not empty
        if (query.trim() === '') {
            showPlaceholder('Your search results will appear here.');
            return;
        }

        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            let results = await response.json();

            // Filter by category on the client-side
            if (category !== 'all') {
                results = results.filter(item => item.category === category);
            }

            renderResults(results);
        } catch (error) {
            console.error("Failed to fetch search results:", error);
            showPlaceholder('An error occurred while searching. Please try again.');
        }
    }

    // --- UI Rendering ---
    function renderResults(results) {
        resultsGrid.innerHTML = ''; // Clear previous results

        if (results.length === 0) {
            showPlaceholder('No results found for your query.');
            return;
        }

        results.forEach(item => {
            const card = createResultCard(item);
            resultsGrid.appendChild(card);
        });

        // Re-initialize lucide icons
        lucide.createIcons();
    }

    function createResultCard(item) {
        const card = document.createElement('a');
        card.href = item.url;
        card.className = 'card';
        card.target = '_blank'; // Open in new tab

        const content = document.createElement('div');
        content.className = 'card-content';

        const title = document.createElement('h3');
        title.className = 'card-title';
        title.textContent = item.title;

        const source = document.createElement('p');
        source.className = 'card-source';
        source.textContent = `Source: ${item.source_url}`;

        const badges = document.createElement('div');
        badges.className = 'metadata-badges';

        // Add badges for metadata if it exists
        if (item.year) badges.innerHTML += `<span class="badge">${item.year}</span>`;
        if (item.quality) badges.innerHTML += `<span class="badge">${item.quality}</span>`;
        if (item.season) badges.innerHTML += `<span class="badge">S${String(item.season).padStart(2, '0')}</span>`;
        if (item.episode) badges.innerHTML += `<span class="badge">E${String(item.episode).padStart(3, '0')}</span>`;

        content.appendChild(title);
        content.appendChild(source);
        content.appendChild(badges);
        card.appendChild(content);

        return card;
    }

    function showPlaceholder(message) {
        resultsGrid.innerHTML = `
            <div class="placeholder">
                <i data-lucide="search-slash"></i>
                <p>${message}</p>
            </div>
        `;
        lucide.createIcons();
    }

    // Initial call to render icons
    lucide.createIcons();
});
