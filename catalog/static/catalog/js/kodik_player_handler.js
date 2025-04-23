// catalog/static/catalog/js/kodik_player_handler.js

// Get data passed from the template via data-* attributes
const playerElement = document.getElementById('kodik-player');
const playerContainer = document.querySelector('.player-container'); // Get the container if needed
const defaultSrc = playerElement.dataset.defaultSrc;
const storageKey = playerElement.dataset.storageKey;
const unknownTranslationText = playerElement.dataset.unknownTranslation; // Get translated text

const resetBtn = document.getElementById('reset-translation-btn');
const currentTranslationDisplay = document.getElementById('current-translation-info');
const currentTranslationTitle = document.getElementById('current-translation-title');

let preferredTranslationId = localStorage.getItem(storageKey);
let currentSrc = defaultSrc;

console.log("Kodik handler loaded. Default src:", defaultSrc, "Storage key:", storageKey); // Debug log

// Function to construct URL with parameters
function getModifiedSrc(baseSrc, translationId) {
    if (!translationId || !baseSrc) return baseSrc; // Add check for baseSrc
    try {
        // Handle protocol-relative URLs robustly
        const absoluteBase = baseSrc.startsWith('//') ? `${window.location.protocol}${baseSrc}` : baseSrc;
        const url = new URL(absoluteBase);
        url.searchParams.set('only_translations', translationId);
        url.searchParams.set('auto_translation', 'true');
        // Return in the original format (protocol-relative or absolute)
        return baseSrc.startsWith('//') ? url.toString().substring(url.protocol.length) : url.toString();
    } catch (e) {
        console.error("Error modifying URL:", e);
        return baseSrc;
    }
}

// Set initial iframe source based on preference
if (preferredTranslationId) {
    console.log(`Found preferred translation ID: ${preferredTranslationId}`);
    currentSrc = getModifiedSrc(defaultSrc, preferredTranslationId);
} else {
    console.log("No preferred translation found, using default.");
}

// Only set src if defaultSrc is valid
if (defaultSrc) {
    playerElement.src = currentSrc;
    console.log("Initial iframe src set to:", currentSrc);
} else {
    console.error("Default source URL is missing or invalid!");
    // Optionally display an error message to the user in the player container
    if (playerContainer) {
        playerContainer.innerHTML = '<p style="color: red; text-align: center; padding: 20px;">Error loading player: Source URL missing.</p>';
    }
}


// Listener for messages from the player iframe
function kodikMessageListener(event) {
    // Basic security check: verify the origin of the message if possible
    // Consider adding the expected origin based on kodik URLs
    // if (event.origin !== 'expected-kodik-domain') return;

    if (event.data && event.data.key === 'kodik_player_current_episode') {
        const value = event.data.value;
        console.log('Received kodik_player_current_episode:', value);
        if (value && value.translation && value.translation.id) {
            const receivedTranslationId = value.translation.id.toString();
            const receivedTranslationTitle = value.translation.title;

            if (currentTranslationTitle) {
                currentTranslationTitle.textContent = receivedTranslationTitle || unknownTranslationText || 'Unknown';
            }
            if (currentTranslationDisplay) {
                currentTranslationDisplay.style.display = 'block';
            }

            localStorage.setItem(storageKey, receivedTranslationId);
            preferredTranslationId = receivedTranslationId;
            console.log(`Saved preferred translation ID: ${receivedTranslationId}`);
        }
    }
    // Add handlers for other events if needed
}

// Attach the listener
if (window.addEventListener) {
    window.addEventListener('message', kodikMessageListener);
} else {
    window.attachEvent('onmessage', kodikMessageListener); // For older IE
}

// Handler for the reset button
if (resetBtn) {
    resetBtn.addEventListener('click', function () {
        console.log('Resetting translation preference...');
        localStorage.removeItem(storageKey);
        preferredTranslationId = null;
        if (currentTranslationDisplay) {
            currentTranslationDisplay.style.display = 'none';
        }
        // Reload iframe with default src
        if (defaultSrc) {
            playerElement.src = defaultSrc;
            console.log("Iframe reloaded with default src:", defaultSrc);
        } else {
            console.error("Cannot reset, default source URL is missing!");
        }

    });
}

// Cleanup listener on page unload (optional but good practice)
window.addEventListener('unload', function () {
    if (window.removeEventListener) {
        window.removeEventListener('message', kodikMessageListener);
    } else {
        window.detachEvent('onmessage', kodikMessageListener);
    }
});