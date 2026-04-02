/**
 * Smart Weather Dashboard - Core Logic
 */

// Global State & Constants
let currentData = null;
let lightningInterval = null;
let windChart = null;
let uvChart = null;
let tempTrendChart = null;
let precipChart = null;
let weatherMap = null;
let mapMarker = null;

// --- Mock Data Service ---
const getMockWeatherData = (city = 'Florida, US') => {
    return {
        city: city,
        temp: 28,
        condition: 'Rainy Storm Clouds',
        conditionCode: 'storm', // clear, clouds, rain, storm, snow
        humidity: 84,
        windSpeed: 7.9,
        uvIndex: 5.5,
        visibility: 3,
        feelsLike: 42,
        sunrise: '5:50 AM',
        sunset: '6:30 PM',
        timestamp: new Date().toLocaleString(),
        lat: 27.6648,
        lon: -81.5158,
        forecast: [
            { day: 'Tuesday', temp: 29, low: 18, condition: 'clouds' },
            { day: 'Wednesday', temp: 21, low: 16, condition: 'storm' },
            { day: 'Thursday', temp: 24, low: 20, condition: 'clear' },
            { day: 'Friday', temp: 30, low: 17, condition: 'clouds' },
            { day: 'Saturday', temp: 27, low: 19, condition: 'rain' },
            { day: 'Sunday', temp: 26, low: 18, condition: 'clouds' },
            { day: 'Monday', temp: 25, low: 17, condition: 'clear' }
        ]
    };
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    initMap();
    setupEventListeners();

    // Initial Load: Try Geolocation
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => updateWeatherByCoords(pos.coords.latitude, pos.coords.longitude),
            () => updateWeatherByCity('Florida, US')
        );
    } else {
        updateWeatherByCity('Florida, US');
    }
});

const setupEventListeners = () => {
    const searchInput = document.querySelector('input[type="text"]');
    const geoBtn = document.querySelector('button:has(.lucide-locate-fixed)');

    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            if (e.key === 'Enter') updateWeatherByCity(searchInput.value);
        });
    }

    if (geoBtn) {
        geoBtn.addEventListener('click', () => {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => updateWeatherByCoords(pos.coords.latitude, pos.coords.longitude)
                );
            }
        });
    }

    // Sidebar Navigation
    document.querySelectorAll('[data-tab]').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.getAttribute('data-tab');
            switchTab(tabName);

            // Update active state in UI
            document.querySelectorAll('[data-tab]').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
        });
    });
};

const switchTab = (tabName) => {
    const sections = ['dashboard-section', 'map-section', 'stats-section', 'calendar-section', 'settings-section'];
    sections.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });

    const activeSection = document.getElementById(`${tabName}-section`);
    if (activeSection) {
        activeSection.classList.remove('hidden');

        // Handle specific section refreshes
        if (tabName === 'map' && weatherMap) {
            setTimeout(() => {
                weatherMap.invalidateSize();
                if (currentData) weatherMap.setView([currentData.lat, currentData.lon], 10);
            }, 100);
        }
    }
};

// --- Weather Updates ---
const updateWeatherByCity = (city) => {
    if (!city) return;
    const data = getMockWeatherData(city);
    updateUI(data);
};

const updateWeatherByCoords = (lat, lon) => {
    const data = getMockWeatherData(`Location (${lat.toFixed(2)}, ${lon.toFixed(2)})`);
    data.lat = lat;
    data.lon = lon;
    updateUI(data);
};

const updateUI = (data) => {
    currentData = data;

    // Basic Info
    const tempEl = document.querySelector('.text-8xl');
    if (tempEl) tempEl.textContent = `${data.temp}°c`;

    const condEl = document.querySelector('.text-2xl.font-medium.text-white');
    if (condEl) condEl.textContent = data.condition;

    const cityEl = document.querySelector('.city-name');
    if (cityEl) cityEl.textContent = data.city;

    const timeEl = document.querySelector('.current-time');
    if (timeEl) timeEl.textContent = data.timestamp;

    // Highlights
    const humVal = document.getElementById('humidity-val');
    if (humVal) humVal.textContent = `${data.humidity}%`;

    const windVal = document.getElementById('wind-val');
    if (windVal) windVal.textContent = `${data.windSpeed} km/h`;

    const uvVal = document.getElementById('uv-val');
    if (uvVal) uvVal.innerHTML = `${data.uvIndex} <span class="text-sm font-normal">uv</span>`;

    const visVal = document.getElementById('visibility-val');
    if (visVal) visVal.textContent = `0${data.visibility} km`;

    const feelsVal = document.getElementById('feels-like-val');
    if (feelsVal) feelsVal.textContent = `${data.feelsLike}°`;

    // Smart Suggestion
    updateSmartSuggestion(data);

    // Dynamic Background
    updateDynamicBackground(data.conditionCode);

    // Update Charts
    updateCharts(data);

    // Update Map
    if (weatherMap) {
        weatherMap.setView([data.lat, data.lon], 10);
        if (mapMarker) {
            mapMarker.setLatLng([data.lat, data.lon]);
        } else {
            mapMarker = L.marker([data.lat, data.lon]).addTo(weatherMap);
        }
    }

    // Update Sun Arc
    updateSunArc(data.sunrise, data.sunset);
};

const updateCharts = (data) => {
    if (windChart) {
        windChart.updateSeries([{
            name: 'Wind Speed',
            data: [12, 19, 13, 15, 20, 17, 22].map(v => v + Math.floor(Math.random() * 5))
        }]);
    }
    if (uvChart) {
        uvChart.updateSeries([data.uvIndex * 10]);
    }
    if (tempTrendChart) {
        tempTrendChart.updateSeries([{
            name: 'Temperature',
            data: [20, 23, 21, 25, 28, 26, 24].map(v => v + (Math.random() * 4 - 2))
        }]);
    }
    if (precipChart) {
        precipChart.updateSeries([{
            name: 'Probability',
            data: [10, 40, 30, 70, 20, 10, 5].map(v => v + Math.floor(Math.random() * 20))
        }]);
    }
};

const updateSunArc = (sunrise, sunset) => {
    const sunDot = document.getElementById('sun-dot');
    const path = document.querySelector('#sun-arc path:last-child');
    if (!sunDot || !path) return;

    // Simulate progress: 6am to 6pm is 0 to 1
    const now = new Date();
    const hours = now.getHours() + now.getMinutes() / 60;

    let progress = (hours - 6) / 12;
    if (progress < 0) progress = 0;
    if (progress > 1) progress = 1;

    const totalLength = path.getTotalLength();
    const offset = totalLength - (progress * totalLength);

    path.style.strokeDasharray = totalLength;
    path.style.strokeDashoffset = offset;

    const point = path.getPointAtLength(progress * totalLength);
    sunDot.setAttribute('cx', point.x);
    sunDot.setAttribute('cy', point.y);
};

const updateSmartSuggestion = (data) => {
    const tipContainer = document.querySelector('.bg-blue-500\\/10');
    if (!tipContainer) return;
    const tipText = tipContainer.querySelector('p');
    if (!tipText) return;

    let tip = "Enjoy the beautiful weather!";
    if (data.conditionCode === 'rain' || data.conditionCode === 'storm') {
        tip = "It's going to rain, don't forget your umbrella!";
    } else if (data.temp > 30) {
        tip = "Stay hydrated! It's quite hot outside.";
    } else if (data.uvIndex > 7) {
        tip = "High UV index. Wear sunscreen!";
    }

    tipText.textContent = tip;
};

// --- Animations ---
const updateDynamicBackground = (code) => {
    const container = document.getElementById('weather-bg');
    if (!container) return;
    container.innerHTML = '';

    if (lightningInterval) {
        clearInterval(lightningInterval);
        lightningInterval = null;
    }

    if (code === 'rain' || code === 'storm') createRain();
    if (code === 'clouds' || code === 'storm') createClouds();
    if (code === 'storm') createLightning();
};

const createRain = () => {
    const container = document.getElementById('weather-bg');
    for (let i = 0; i < 60; i++) {
        const drop = document.createElement('div');
        drop.className = 'rain-drop';
        drop.style.left = `${Math.random() * 100}%`;
        drop.style.animationDuration = `${0.5 + Math.random() * 0.5}s`;
        drop.style.animationDelay = `${Math.random() * 2}s`;
        container.appendChild(drop);
    }
};

const createClouds = () => {
    const container = document.getElementById('weather-bg');
    for (let i = 0; i < 4; i++) {
        const cloud = document.createElement('div');
        cloud.className = 'cloud-particle';
        cloud.style.top = `${Math.random() * 40}%`;
        cloud.style.width = `${200 + Math.random() * 300}px`;
        cloud.style.height = `${100 + Math.random() * 150}px`;
        cloud.style.animationDuration = `${30 + Math.random() * 30}s`;
        cloud.style.animationDelay = `-${Math.random() * 30}s`;
        container.appendChild(cloud);
    }
};

const createLightning = () => {
    const container = document.getElementById('weather-bg');
    const flash = document.createElement('div');
    flash.className = 'lightning-flash';
    container.appendChild(flash);

    lightningInterval = setInterval(() => {
        if (Math.random() > 0.94) {
            flash.style.opacity = '0.3';
            setTimeout(() => { flash.style.opacity = '0'; }, 50);
            setTimeout(() => { flash.style.opacity = '0.4'; }, 100);
            setTimeout(() => { flash.style.opacity = '0'; }, 200);
        }
    }, 1000);
};

// --- Charts ---
const initCharts = () => {
    // Wind Chart
    const windEl = document.querySelector("#wind-chart");
    if (windEl) {
        windChart = new ApexCharts(windEl, {
            series: [{ name: 'Wind Speed', data: [12, 19, 13, 15, 20, 17, 22] }],
            chart: { type: 'line', height: 120, sparkline: { enabled: true }, animations: { enabled: true } },
            stroke: { curve: 'smooth', width: 3, colors: ['#3b82f6'] },
            tooltip: { theme: 'dark' }
        });
        windChart.render();
    }

    // UV Chart
    const uvEl = document.querySelector("#uv-chart");
    if (uvEl) {
        uvChart = new ApexCharts(uvEl, {
            series: [55],
            chart: { height: 150, type: 'radialBar', sparkline: { enabled: true } },
            plotOptions: {
                radialBar: {
                    startAngle: -90, endAngle: 90,
                    track: { background: "rgba(255,255,255,0.1)", strokeWidth: '97%' },
                    dataLabels: { name: { show: false }, value: { offsetY: -2, fontSize: '18px', color: '#fff' } }
                }
            },
            fill: { colors: ['#3b82f6'] }
        });
        uvChart.render();
    }

    // Stats: Temp Trend
    const tempEl = document.querySelector("#temp-trend-chart");
    if (tempEl) {
        tempTrendChart = new ApexCharts(tempEl, {
            series: [{ name: 'Temperature', data: [20, 23, 21, 25, 28, 26, 24] }],
            chart: { type: 'area', height: '100%', foreColor: '#94a3b8', toolbar: { show: false } },
            colors: ['#3b82f6'],
            fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.7, opacityTo: 0.1 } },
            dataLabels: { enabled: false },
            stroke: { curve: 'smooth' },
            xaxis: { categories: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] },
            grid: { borderColor: 'rgba(255,255,255,0.05)' }
        });
        tempTrendChart.render();
    }

    // Stats: Precipitation
    const precipEl = document.querySelector("#precip-chart");
    if (precipEl) {
        precipChart = new ApexCharts(precipEl, {
            series: [{ name: 'Probability', data: [10, 40, 30, 70, 20, 10, 5] }],
            chart: { type: 'bar', height: '100%', foreColor: '#94a3b8', toolbar: { show: false } },
            colors: ['#6366f1'],
            plotOptions: { bar: { borderRadius: 6, columnWidth: '50%' } },
            dataLabels: { enabled: false },
            xaxis: { categories: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] },
            grid: { borderColor: 'rgba(255,255,255,0.05)' }
        });
        precipChart.render();
    }
};

// --- Map ---
const initMap = () => {
    const container = document.getElementById('map-container');
    if (!container) return;

    weatherMap = L.map(container, { zoomControl: false }).setView([27.6648, -81.5158], 7);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(weatherMap);

    mapMarker = L.marker([27.6648, -81.5158]).addTo(weatherMap);
};
