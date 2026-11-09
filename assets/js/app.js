/**
 * LE HUB RÉVISION - SCRIPT GLOBAL
 * Gestion du Thème Clair/Sombre, de la progression et de l'impression
 */

// 1. Initialisation du Thème (Clair par défaut, ou choix sauvegardé)
function initTheme() {
    const savedTheme = localStorage.getItem('hub_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
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
        btn.setAttribute('title', theme === 'dark' ? 'Passer en mode clair' : 'Passer en mode sombre');
    }
}

// 2. Gestion de la Progression (Checkboxes "Cours Révisé")
function getCompletedCourses() {
    try {
        return JSON.parse(localStorage.getItem('hub_completed_courses') || '[]');
    } catch {
        return [];
    }
}

function toggleCourseCompletion(courseId) {
    let completed = getCompletedCourses();
    if (completed.includes(courseId)) {
        completed = completed.filter(id => id !== courseId);
    } else {
        completed.push(courseId);
    }
    localStorage.setItem('hub_completed_courses', JSON.stringify(completed));
    updateProgressUI();
}

function updateProgressUI() {
    const completed = getCompletedCourses();
    const allCourses = ['politique-famille', 'politique-ville'];
    const count = completed.filter(id => allCourses.includes(id)).length;
    const total = allCourses.length;
    const percent = Math.round((count / total) * 100);

    const progressFill = document.getElementById('progressFill');
    const progressCount = document.getElementById('progressCount');
    const progressPercent = document.getElementById('progressPercent');

    if (progressFill) progressFill.style.width = percent + '%';
    if (progressCount) progressCount.innerText = `${count} sur ${total} cours maîtrisés`;
    if (progressPercent) progressPercent.innerText = `${percent}%`;

    // Mettre à jour l'état visuel des boutons ou badges sur la page
    allCourses.forEach(id => {
        const checkbox = document.getElementById('chk-' + id);
        if (checkbox) checkbox.checked = completed.includes(id);
    });
}

// 3. Impression de la Fiche Bristol
function printBristol() {
    window.print();
}

// Exécuter au chargement
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    updateProgressUI();
});
