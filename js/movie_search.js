// Globals
let movieList = [];

// DOM Elements
let searchInput;
let resultsContainer;
let viewToggle;
let movieModal;
let modalTitle;
let modalDownloadLink;
let closeModal;

function renderResults(movies) {
    resultsContainer.innerHTML = '';

    if (movies.length === 0) {
        resultsContainer.innerHTML = '<p class="text-center text-gray-500 col-span-full">No movies found matching your search.</p>';
        return;
    }

    movies.forEach(movie => {
        const movieCard = document.createElement('div');
        movieCard.className = 'movie-card bg-white rounded-lg shadow-md p-4 cursor-pointer hover:shadow-lg transition-shadow';
        movieCard.dataset.url = movie.url;

        movieCard.innerHTML = `
            <h3 class="font-bold text-lg text-gray-800 truncate">${movie.title}</h3>
        `;

        movieCard.addEventListener('click', () => showModal(movie.title, movie.url));
        resultsContainer.appendChild(movieCard);
    });
}

function handleSearch() {
    const searchTerm = searchInput.value.toLowerCase();
    const filteredMovies = movieList.filter(movie =>
        movie.title.toLowerCase().includes(searchTerm)
    );
    renderResults(filteredMovies);
}

function toggleView() {
    if (viewToggle.checked) {
        resultsContainer.classList.add('grid-view');
        resultsContainer.classList.remove('list-view');
    } else {
        resultsContainer.classList.add('list-view');
        resultsContainer.classList.remove('grid-view');
    }
}

function showModal(title, downloadLink) {
    modalTitle.textContent = title;
    modalDownloadLink.href = downloadLink;
    movieModal.classList.remove('hidden');
}

function hideModal() {
    movieModal.classList.add('hidden');
}


document.addEventListener('DOMContentLoaded', () => {
    // Assign DOM elements
    searchInput = document.getElementById('searchInput');
    resultsContainer = document.getElementById('resultsContainer');
    viewToggle = document.getElementById('viewToggle');
    movieModal = document.getElementById('movieModal');
    modalTitle = document.getElementById('modalTitle');
    modalDownloadLink = document.getElementById('modalDownloadLink');
    closeModal = document.getElementById('closeModal');

    // Add event listeners
    searchInput.addEventListener('keyup', handleSearch);
    viewToggle.addEventListener('change', toggleView);
    closeModal.addEventListener('click', hideModal);
    movieModal.addEventListener('click', (e) => {
        if (e.target === movieModal) {
            hideModal();
        }
    });

    // Load movie data
    movieList = movieData;

    // Set initial view
    toggleView();

    // Initial render
    renderResults(movieList);
});
