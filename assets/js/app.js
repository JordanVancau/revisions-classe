/**
 * Hub Révision - Theme & Utilities
 */

function initTheme() {
    const saved = localStorage.getItem('hub_theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('hub_theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('themeToggleBtn');
    if (btn) {
        btn.innerHTML = theme === 'dark' ? '☀️' : '🌙';
        btn.setAttribute('aria-label', theme === 'dark' ? 'Passer au mode clair' : 'Passer au mode sombre');
    }
}

document.addEventListener('DOMContentLoaded', initTheme);
