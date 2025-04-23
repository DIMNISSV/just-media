// static/js/theme_switcher.js

(() => {
    'use strict';

    const THEME_STORAGE_KEY = 'theme';
    const THEME_ATTR = 'data-bs-theme';
    const LIGHT_THEME = 'light';
    const DARK_THEME = 'dark';

    const themeSwitcherBtn = document.getElementById('theme-switcher-btn');
    const themeSwitcherText = document.getElementById('theme-switcher-text'); // Optional text display

    // --- Helper Functions ---
    const getStoredTheme = () => localStorage.getItem(THEME_STORAGE_KEY);
    const setStoredTheme = theme => localStorage.setItem(THEME_STORAGE_KEY, theme);

    const getPreferredTheme = () => {
        const storedTheme = getStoredTheme();
        if (storedTheme) {
            return storedTheme;
        }
        // Fallback to OS preference
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK_THEME : LIGHT_THEME;
    };

    const applyTheme = theme => {
        document.documentElement.setAttribute(THEME_ATTR, theme);
        console.log(`Theme applied: ${theme}`); // Debug log

        // Update button text/appearance (optional)
        if (themeSwitcherText) {
            themeSwitcherText.textContent = theme === DARK_THEME ? 'Light' : 'Dark'; // Suggest switching to the opposite
        }
        // You could also change button icon or style here
    };

    // --- Initialization ---
    const currentTheme = getPreferredTheme();
    applyTheme(currentTheme); // Apply theme on initial load

    // --- Event Listeners ---
    // Listener for manual theme toggle via button
    if (themeSwitcherBtn) {
        themeSwitcherBtn.addEventListener('click', () => {
            const currentAppliedTheme = document.documentElement.getAttribute(THEME_ATTR);
            const newTheme = currentAppliedTheme === DARK_THEME ? LIGHT_THEME : DARK_THEME;
            setStoredTheme(newTheme);
            applyTheme(newTheme);
        });
    } else {
        console.warn('Theme switcher button not found.');
    }

    // Optional: Listener for changes in OS theme preference
    // This will only change the theme if the user hasn't manually set one via the button
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const storedTheme = getStoredTheme();
        if (!storedTheme) { // Only react if no theme is manually stored
            const osTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK_THEME : LIGHT_THEME;
            applyTheme(osTheme);
            console.log(`Theme changed based on OS preference: ${osTheme}`);
        }
    });

})(); // Immediately Invoked Function Expression (IIFE)