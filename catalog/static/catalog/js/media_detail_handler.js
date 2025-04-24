// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    const playerPlaceholder = document.getElementById('player-placeholder');
    const mediaDescription = document.getElementById('media-description');
    const episodesContainer = document.getElementById('seasons-tab-content');
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplate = document.getElementById('player-url-template')?.dataset.url;

    let currentEpisodeElement = null;

    console.log("Media detail handler loaded.");

    function generatePlayerUrl(linkPk) {
        if (!playerUrlTemplate || !linkPk) return null;
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
            playerPlaceholder.innerHTML = '<p class="text-danger">Error loading player.</p>';
        }
    }

    function highlightEpisode(episodeElement) {
        if (currentEpisodeElement) {
            currentEpisodeElement.classList.remove('border', 'border-primary', 'border-3');
        }
        if (episodeElement) {
            episodeElement.classList.add('border', 'border-primary', 'border-3');
            currentEpisodeElement = episodeElement;
            updateNavButtons();
        } else {
            currentEpisodeElement = null;
            updateNavButtons();
        }
    }

    function findEpisodeElement(seasonNum, episodeNum) {
        return episodesContainer.querySelector(`.episode-selector[data-season-num='${seasonNum}'][data-episode-num='${episodeNum}']`);
    }

    function findNextEpisodeElement(currentElement) {
        if (!currentElement) return null;

        const nextSibling = currentElement.closest('.col').nextElementSibling;
        if (nextSibling && nextSibling.querySelector('.episode-selector')) {
            return nextSibling.querySelector('.episode-selector');
        } else {
            // Try next season
            const currentTabPane = currentElement.closest('.tab-pane');
            const nextTabPane = currentTabPane.nextElementSibling;
            if (nextTabPane && nextTabPane.classList.contains('tab-pane')) {
                const nextTabButtonId = nextTabPane.getAttribute('aria-labelledby');
                const nextTabButton = document.getElementById(nextTabButtonId);
                if (nextTabButton) {
                    const tab = new bootstrap.Tab(nextTabButton);
                    tab.show();
                }
                return nextTabPane.querySelector('.episode-selector');
            }
        }
        return null;
    }

    function findPrevEpisodeElement(currentElement) {
        if (!currentElement) return null;

        const prevSibling = currentElement.closest('.col').previousElementSibling;
        if (prevSibling && prevSibling.querySelector('.episode-selector')) {
            return prevSibling.querySelector('.episode-selector');
        } else {
            // Try previous season
            const currentTabPane = currentElement.closest('.tab-pane');
            const prevTabPane = currentTabPane.previousElementSibling;
            if (prevTabPane && prevTabPane.classList.contains('tab-pane')) {
                const prevTabButtonId = prevTabPane.getAttribute('aria-labelledby');
                const prevTabButton = document.getElementById(prevTabButtonId);
                if (prevTabButton) {
                    const tab = new bootstrap.Tab(prevTabButton);
                    tab.show();
                }
                const episodesInPrev = prevTabPane.querySelectorAll('.episode-selector');
                return episodesInPrev.length > 0 ? episodesInPrev[episodesInPrev.length - 1] : null;
            }
        }
        return null;
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
                event.preventDefault();
                const linkPk = episodeCard.dataset.linkPk;

                if (linkPk) {
                    loadPlayer(linkPk);
                    highlightEpisode(episodeCard);
                } else {
                    console.warn('No link PK found for episode:', episodeCard.dataset.episodePk);
                    if (playerPlaceholder) playerPlaceholder.innerHTML = '<p class="text-warning">No playable source found for this episode.</p>';
                    highlightEpisode(null);
                }
            }
        });
    }

    if (nextEpisodeBtn) {
        nextEpisodeBtn.addEventListener('click', () => {
            const nextElement = findNextEpisodeElement(currentEpisodeElement);
            if (nextElement) {
                nextElement.click();
            }
        });
    }

    if (prevEpisodeBtn) {
        prevEpisodeBtn.addEventListener('click', () => {
            const prevElement = findPrevEpisodeElement(currentEpisodeElement);
            if (prevElement) {
                prevElement.click();
            }
        });
    }

    updateNavButtons();

});