// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    const playerPlaceholder = document.getElementById('player-placeholder');
    const mediaDescription = document.getElementById('media-description');
    const episodesContainer = document.getElementById('seasons-tab-content');
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplate = document.getElementById('player-url-template')?.dataset.url; // base url like /catalog/play/0/

    let currentEpisodeElement = null;

    console.log("Media detail handler loaded.");

    function generatePlayerUrl(linkPk) {
        if (!playerUrlTemplate || !linkPk) return null;
        // Replace the placeholder '0' with the actual link PK
        return playerUrlTemplate.replace('/0/', `/${linkPk}/`);
    }

    function loadPlayer(linkPk) {
        const playerUrl = generatePlayerUrl(linkPk);
        console.log(`Attempting to load player for link PK: ${linkPk}, URL: ${playerUrl}`);
        if (playerUrl && playerPlaceholder) {
            playerPlaceholder.innerHTML = `
                <div class="player-container" style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background: #000;">
                    <iframe src="${playerUrl}"
                            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
                            frameborder="0" scrolling="no" allowfullscreen="allowfullscreen"
                            webkitallowfullscreen="webkitallowfullscreen" mozallowfullscreen="mozallowfullscreen">
                    </iframe>
                </div>`;
            // Hide description
            if (mediaDescription) {
                mediaDescription.style.display = 'none';
            }
        } else {
            console.error('Could not generate player URL or placeholder not found.');
            // Optionally show an error message in the placeholder
            playerPlaceholder.innerHTML = '<p class="text-danger">Error loading player.</p>';
        }
    }

    function highlightEpisode(episodeElement) {
        // Remove highlight from previous
        if (currentEpisodeElement) {
            currentEpisodeElement.classList.remove('border', 'border-primary', 'border-3'); // Example highlight
        }
        // Add highlight to new
        if (episodeElement) {
            episodeElement.classList.add('border', 'border-primary', 'border-3');
            currentEpisodeElement = episodeElement;
            // Update next/prev button states
            updateNavButtons();
        } else {
            currentEpisodeElement = null;
            updateNavButtons(); // Disable buttons if no episode selected
        }
    }

    function findEpisodeElement(seasonNum, episodeNum) {
        return episodesContainer.querySelector(`.episode-selector[data-season-num='${seasonNum}'][data-episode-num='${episodeNum}']`);
    }

    function findNextEpisodeElement(currentElement) {
        if (!currentElement) return null;

        const nextSibling = currentElement.closest('.col').nextElementSibling;
        if (nextSibling && nextSibling.querySelector('.episode-selector')) {
            return nextSibling.querySelector('.episode-selector'); // Next episode in the same season
        } else {
            // Try next season
            const currentTabPane = currentElement.closest('.tab-pane');
            const nextTabPane = currentTabPane.nextElementSibling;
            if (nextTabPane && nextTabPane.classList.contains('tab-pane')) {
                // Activate next tab (visually)
                const nextTabButtonId = nextTabPane.getAttribute('aria-labelledby');
                const nextTabButton = document.getElementById(nextTabButtonId);
                if (nextTabButton) {
                    const tab = new bootstrap.Tab(nextTabButton); // Use Bootstrap's Tab API
                    tab.show();
                }
                // Return first episode of next season
                return nextTabPane.querySelector('.episode-selector');
            }
        }
        return null; // No next episode found
    }

    function findPrevEpisodeElement(currentElement) {
        if (!currentElement) return null;

        const prevSibling = currentElement.closest('.col').previousElementSibling;
        if (prevSibling && prevSibling.querySelector('.episode-selector')) {
            return prevSibling.querySelector('.episode-selector'); // Previous episode in the same season
        } else {
            // Try previous season
            const currentTabPane = currentElement.closest('.tab-pane');
            const prevTabPane = currentTabPane.previousElementSibling;
            if (prevTabPane && prevTabPane.classList.contains('tab-pane')) {
                // Activate previous tab
                const prevTabButtonId = prevTabPane.getAttribute('aria-labelledby');
                const prevTabButton = document.getElementById(prevTabButtonId);
                if (prevTabButton) {
                    const tab = new bootstrap.Tab(prevTabButton);
                    tab.show();
                }
                // Return last episode of previous season
                const episodesInPrev = prevTabPane.querySelectorAll('.episode-selector');
                return episodesInPrev.length > 0 ? episodesInPrev[episodesInPrev.length - 1] : null;
            }
        }
        return null; // No previous episode found
    }


    function updateNavButtons() {
        const nextElement = findNextEpisodeElement(currentEpisodeElement);
        const prevElement = findPrevEpisodeElement(currentEpisodeElement);

        if (nextEpisodeBtn) nextEpisodeBtn.disabled = !nextElement;
        if (prevEpisodeBtn) prevEpisodeBtn.disabled = !prevElement;
    }


    // --- Event Listeners ---
    if (episodesContainer) {
        episodesContainer.addEventListener('click', (event) => {
            const episodeCard = event.target.closest('.episode-selector');
            if (episodeCard) {
                event.preventDefault(); // Prevent default link behavior if it's an <a>
                const linkPk = episodeCard.dataset.linkPk;

                if (linkPk) {
                    loadPlayer(linkPk);
                    highlightEpisode(episodeCard);
                } else {
                    console.warn('No link PK found for episode:', episodeCard.dataset.episodePk);
                    // Optionally show a message to the user
                    if (playerPlaceholder) playerPlaceholder.innerHTML = '<p class="text-warning">No playable source found for this episode.</p>';
                    highlightEpisode(null); // Deselect if no link
                }
            }
        });
    }

    if (nextEpisodeBtn) {
        nextEpisodeBtn.addEventListener('click', () => {
            const nextElement = findNextEpisodeElement(currentEpisodeElement);
            if (nextElement) {
                nextElement.click(); // Simulate click on the next episode card
            }
        });
    }

    if (prevEpisodeBtn) {
        prevEpisodeBtn.addEventListener('click', () => {
            const prevElement = findPrevEpisodeElement(currentEpisodeElement);
            if (prevElement) {
                prevElement.click(); // Simulate click on the previous episode card
            }
        });
    }

    // Initialize button states
    updateNavButtons();

}); // End DOMContentLoaded