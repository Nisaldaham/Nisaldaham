// Dummy data to simulate fetching from an API
const allMaterials = [
    { id: 1, title: 'Algebra Notes', type: 'notes', grade: 10 },
    { id: 2, title: '2023 Physics Paper', type: 'past_papers', grade: 11 },
    { id: 3, title: 'Calculus Worksheet', type: 'worksheets', grade: 12 },
    { id: 4, title: 'Chemistry Video', type: 'videos', grade: 11 },
    { id: 5, title: 'History Notes', type: 'notes', grade: 9 },
];

let currentFilter = '';
let currentSearchTerm = '';

function renderMaterials() {
    const contentArea = document.getElementById('contentArea');
    const loadingState = document.getElementById('loadingState');

    loadingState.style.display = 'none';
    contentArea.innerHTML = '';

    const filteredMaterials = allMaterials.filter(material => {
        const matchesFilter = !currentFilter || material.type === currentFilter;
        const matchesSearch = !currentSearchTerm || material.title.toLowerCase().includes(currentSearchTerm);
        return matchesFilter && matchesSearch;
    });

    if (filteredMaterials.length === 0) {
        contentArea.innerHTML = `<p class="text-center text-gray-500">No materials found.</p>`;
        return;
    }

    const grid = document.createElement('div');
    grid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6';

    filteredMaterials.forEach(material => {
        const card = document.createElement('div');
        card.className = 'bg-white rounded-lg shadow-md p-6';
        card.innerHTML = `
            <h3 class="font-bold text-lg mb-2">${material.title}</h3>
            <p class="text-gray-600">Grade: ${material.grade}</p>
            <p class="text-gray-600 capitalize">Type: ${material.type.replace('_', ' ')}</p>
        `;
        grid.appendChild(card);
    });

    contentArea.appendChild(grid);
}

function filterByType(type) {
    currentFilter = type;

    // Update active state on buttons
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach(button => {
        if (button.dataset.filter === type) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });

    renderMaterials();
}

function searchMaterials(searchTerm) {
    currentSearchTerm = searchTerm.toLowerCase();
    renderMaterials();
}

function showGrades() {
    console.log('showGrades() called. This would typically navigate to the grades view.');
    // Since this is a single page app, we can reset the view
    currentFilter = '';
    currentSearchTerm = '';
    document.getElementById('searchInput').value = '';
    filterByType('');
    renderMaterials();
}

function closeDownloadModal() {
    const modal = document.getElementById('downloadModal');
    if (modal) {
        modal.classList.add('hidden');
    }
    console.log('closeDownloadModal() called.');
}

// Initial render
document.addEventListener('DOMContentLoaded', () => {
    // Set the "All Types" button as active by default
    const allTypesButton = document.querySelector('.filter-btn[data-filter=""]');
    if (allTypesButton) {
        allTypesButton.classList.add('active');
    }
    renderMaterials();
});
