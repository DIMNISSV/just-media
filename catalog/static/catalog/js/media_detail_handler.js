// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    const playerPlaceholder = document.getElementById('player-placeholder');
    const mediaDescription = document.getElementById('media-description');
    const episodesContainer = document.getElementById('seasons-tab-content');
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplate = document.getElementById('player-url-template')?.dataset.url;
    const translationSelectorPlaceholder = document.getElementById('translation-selector-placeholder');
    const episodesLinksDataElement = document.getElementById('episodes-links-data');

    let episodesLinksData = {};
    try {
        if (episodesLinksDataElement) {
            episodesLinksData = JSON.parse(episodesLinksDataElement.textContent || '{}');
        }
    } catch (e) {
        console.error("Error parsing episodes links data:", e);
    }

    let currentEpisodeElement = null;
    let currentSelectedTranslationPk = null; // Keep track of which translation is chosen

    console.log("Media detail handler loaded.");

    function generatePlayerUrl(linkPk) {
        if (!playerUrlTemplate || !linkPk) return null;
        return playerUrlTemplate.replace('/0/', `/${linkPk}/`);
    }

    function loadPlayer(linkPk) {
        const playerUrl = generatePlayerUrl(linkPk);
        console.log(`Attempting to load player for link PK: ${linkPk}, URL: ${playerUrl}`);
        if (playerUrl && playerPlaceholder) {
            // Remember selection before loading (or maybe after successful load?)
            const episodePk = currentEpisodeElement?.dataset.episodePk;
            // TODO: Implement localStorage saving in next commit

            playerPlaceholder.innerHTML = `
                <div class="player-container" style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background: #000;">
                    <iframe src="${playerUrl}"
                            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
                            frameborder="0" scrolling="no" allowfullscreen="allowfullscreen"
                            webkitallowfullscreen="webkitallowfullscreen" mozallowfullscreen="mozallowfullscreen"
                            loading="lazy"> {/* Added lazy loading */}
                    </iframe>
                </div>`;
            if (mediaDescription) {
                mediaDescription.style.display = 'none';
            }
        } else {
            console.error('Could not generate player URL or placeholder not found.');
            playerPlaceholder.innerHTML = '<p class="text-danger">Error loading player.</p>';
        }
    }

    function displayTranslationOptions(episodePk) {
        if (!translationSelectorPlaceholder) return;

        const links = episodesLinksData[episodePk] || [];
        console.log(`Translations found for episode PK ${episodePk}:`, links);

        if (links.length > 0) {
            let buttonsHtml = '<span class="me-2">Choose translation:</span>'; // i18n needed here
            links.forEach(link => {
                // Add quality info if available
                const quality = link.quality ? `(${link.quality})` : '';
                buttonsHtml += `
                    <button class="btn btn-sm btn-outline-primary me-1 mb-1 translation-btn"
                            data-link-pk="${link.link_pk}"
                            data-translation-id="${link.translation_id}">
                        ${link.translation_title} ${quality}
                    </button>`;
            });
            translationSelectorPlaceholder.innerHTML = buttonsHtml;
            // Clear player placeholder until translation is selected
            playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">Select a translation</div>'; // i18n needed
        } else {
            translationSelectorPlaceholder.innerHTML = '<span class="text-warning">No translations found for this episode.</span>'; // i18n needed
            playerPlaceholder.innerHTML = ''; // Clear player placeholder
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

    function highlightTranslationButton(buttonElement) {
        // Remove active state from previous buttons in the container
        translationSelectorPlaceholder.querySelectorAll('.translation-btn.active').forEach(btn => {
            btn.classList.remove('active');
            btn.classList.replace('btn-primary', 'btn-outline-primary'); // Revert style
        });
        // Add active state to the clicked button
        if (buttonElement) {
            buttonElement.classList.add('active');
            buttonElement.classList.replace('btn-outline-primary', 'btn-primary'); // Change style
        }
    }


    function findEpisodeElement(seasonNum, episodeNum) {
        // Ensure episodesContainer is valid before querying
        if (!episodesContainer) return null;
        return episodesContainer.querySelector(`.episode-selector[data-season-num='${seasonNum}'][data-episode-num='${episodeNum}']`);
    }

    function findNextEpisodeElement(currentElement) {
        if (!currentElement) return null;
        const currentContainer = currentElement.closest('.episodes-grid');
        if (!currentContainer) return null;

        const nextSibling = currentElement.closest('.col').nextElementSibling;
        if (nextSibling && nextSibling.querySelector('.episode-selector')) {
            return nextSibling.querySelector('.episode-selector');
        } else {
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const nextTabPane = currentTabPane.nextElementSibling;
            if (nextTabPane && nextTabPane.classList.contains('tab-pane')) {
                const nextTabButtonId = nextTabPane.getAttribute('aria-labelledby');
                const nextTabButton = document.getElementById(nextTabButtonId);
                if (nextTabButton) {
                    try {
                        new bootstrap.Tab(nextTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
                }
                return nextTabPane.querySelector('.episode-selector');
            }
        }
        return null;
    }

    function findPrevEpisodeElement(currentElement) {
        if (!currentElement) return null;
        const currentContainer = currentElement.closest('.episodes-grid');
        if (!currentContainer) return null;

        const prevSibling = currentElement.closest('.col').previousElementSibling;
        if (prevSibling && prevSibling.querySelector('.episode-selector')) {
            return prevSibling.querySelector('.episode-selector');
        } else {
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const prevTabPane = currentTabPane.previousElementSibling;
            if (prevTabPane && prevTabPane.classList.contains('tab-pane')) {
                const prevTabButtonId = prevTabPane.getAttribute('aria-labelledby');
                const prevTabButton = document.getElementById(prevTabButtonId);
                if (prevTabButton) {
                    try {
                        new bootstrap.Tab(prevTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
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
        // Handle episode selection
        episodesContainer.addEventListener('click', (event) => {
            const episodeCard = event.target.closest('.episode-selector');
            if (episodeCard) {
                event.preventDefault();
                const episodePk = episodeCard.dataset.episodePk;

                // Highlight the selected episode immediately
                highlightEpisode(episodeCard);

                // Display translation options for this episode
                displayTranslationOptions(episodePk);

                // Clear player placeholder until translation is chosen
                if (playerPlaceholder) {
                    playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">Select a translation</div>'; // i18n needed
                }
                if (mediaDescription) { // Show description again when episode changes before translation selected
                    mediaDescription.style.display = 'block';
                }
            }
        });
    }

    // Handle translation selection
    if (translationSelectorPlaceholder) {
        translationSelectorPlaceholder.addEventListener('click', (event) => {
            const translationButton = event.target.closest('.translation-btn');
            if (translationButton) {
                event.preventDefault();
                const linkPk = translationButton.dataset.linkPk;
                currentSelectedTranslationPk = linkPk; // Store the chosen link PK

                if (linkPk) {
                    loadPlayer(linkPk);
                    highlightTranslationButton(translationButton);
                } else {
                    console.error("Translation button clicked but no link PK found.");
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

}); // End DOMContentLoaded