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
    const mediaPk = episodesContainer?.dataset.mediaPk; // <<< Get media item PK

    let episodesLinksData = {};
    try {
        if (episodesLinksDataElement) {
            episodesLinksData = JSON.parse(episodesLinksDataElement.textContent || '{}');
        }
    } catch (e) {
        console.error("Error parsing episodes links data:", e);
    }

    let currentEpisodeElement = null;
    let currentSelectedTranslationId = null; // Store translation *ID*, not link PK

    // --- LocalStorage Keys ---
    const lastEpisodeKey = mediaPk ? `last_watched_episode_${mediaPk}` : null;
    const lastTranslationKey = mediaPk ? `last_selected_translation_${mediaPk}` : null;

    console.log("Media detail handler loaded. Media PK:", mediaPk);

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
                            webkitallowfullscreen="webkitallowfullscreen" mozallowfullscreen="mozallowfullscreen"
                            loading="lazy">
                    </iframe>
                </div>`;
            if (mediaDescription) {
                mediaDescription.style.display = 'none';
            }
            // --- Save to localStorage AFTER successful load attempt ---
            if (currentEpisodeElement && lastEpisodeKey) {
                const episodePk = currentEpisodeElement.dataset.episodePk;
                localStorage.setItem(lastEpisodeKey, episodePk);
                console.log(`Saved last episode PK: ${episodePk} to ${lastEpisodeKey}`);
            }
            if (currentSelectedTranslationId && lastTranslationKey) {
                localStorage.setItem(lastTranslationKey, currentSelectedTranslationId);
                console.log(`Saved last translation ID: ${currentSelectedTranslationId} to ${lastTranslationKey}`);
            }

        } else {
            console.error('Could not generate player URL or placeholder not found.');
            playerPlaceholder.innerHTML = '<p class="text-danger">Error loading player.</p>';
        }
    }

    function displayTranslationOptions(episodePk, preselectTranslationId = null) {
        if (!translationSelectorPlaceholder) return;

        const links = episodesLinksData[episodePk] || [];
        console.log(`Translations found for episode PK ${episodePk}:`, links);

        let buttonsHtml = '';
        let translationToLoadPk = null;

        if (links.length > 0) {
            buttonsHtml = '<span class="me-2">Choose translation:</span>';
            links.forEach(link => {
                const quality = link.quality ? `(${link.quality})` : '';
                const isSelected = preselectTranslationId && link.translation_id == preselectTranslationId;
                const btnClass = isSelected ? 'btn-primary active' : 'btn-outline-primary'; // Pre-select style

                buttonsHtml += `
                    <button class="btn btn-sm ${btnClass} me-1 mb-1 translation-btn"
                            data-link-pk="${link.link_pk}"
                            data-translation-id="${link.translation_id}">
                        ${link.translation_title} ${quality}
                    </button>`;

                if (isSelected) {
                    translationToLoadPk = link.link_pk; // Mark this one to load automatically
                    currentSelectedTranslationId = link.translation_id.toString(); // Store preselected ID
                }
            });
            translationSelectorPlaceholder.innerHTML = buttonsHtml;
            // Don't clear player yet if pre-selecting
            if (!translationToLoadPk) {
                playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">Select a translation</div>';
            }

        } else {
            translationSelectorPlaceholder.innerHTML = '<span class="text-warning">No translations found for this episode.</span>';
            playerPlaceholder.innerHTML = '';
        }
        return translationToLoadPk; // Return PK if preselection happened
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
        translationSelectorPlaceholder.querySelectorAll('.translation-btn.active').forEach(btn => {
            btn.classList.remove('active');
            btn.classList.replace('btn-primary', 'btn-outline-primary');
        });
        if (buttonElement) {
            buttonElement.classList.add('active');
            buttonElement.classList.replace('btn-outline-primary', 'btn-primary');
        }
    }


    function findEpisodeElementByPk(episodePk) {
        if (!episodesContainer || !episodePk) return null;
        return episodesContainer.querySelector(`.episode-selector[data-episode-pk='${episodePk}']`);
    }

    function findEpisodeElement(seasonNum, episodeNum) {
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

    function restoreLastWatchedState() {
        if (!lastEpisodeKey) return; // Need media PK

        const lastEpisodePk = localStorage.getItem(lastEpisodeKey);
        if (lastEpisodePk) {
            const lastEpisodeElement = findEpisodeElementByPk(lastEpisodePk);
            if (lastEpisodeElement) {
                console.log(`Restoring last watched episode: PK ${lastEpisodePk}`);
                // Activate the season tab if needed
                const targetTabPaneId = lastEpisodeElement.closest('.tab-pane')?.id;
                const targetTabButton = targetTabPaneId ? document.querySelector(`button[data-bs-target='#${targetTabPaneId}']`) : null;
                if (targetTabButton) {
                    try {
                        new bootstrap.Tab(targetTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
                }

                // Highlight episode and display translations
                highlightEpisode(lastEpisodeElement);
                const lastTranslationId = lastTranslationKey ? localStorage.getItem(lastTranslationKey) : null;
                const translationLinkPkToLoad = displayTranslationOptions(lastEpisodePk, lastTranslationId); // Pass last translation ID

                // If a matching translation was found and pre-selected, load the player
                if (translationLinkPkToLoad) {
                    console.log(`Restoring last selected translation: ID ${lastTranslationId}, loading link PK ${translationLinkPkToLoad}`);
                    loadPlayer(translationLinkPkToLoad);
                    // Ensure the correct translation button is highlighted
                    const translationButton = translationSelectorPlaceholder?.querySelector(`.translation-btn[data-translation-id='${lastTranslationId}']`);
                    highlightTranslationButton(translationButton);
                } else if (lastTranslationId) {
                    console.log(`Last selected translation (ID ${lastTranslationId}) not found for restored episode ${lastEpisodePk}.`);
                }

            } else {
                console.log(`Could not find last watched episode element (PK ${lastEpisodePk}) in DOM.`);
            }
        } else {
            console.log("No last watched episode found in localStorage.");
        }
    }


    // --- Event Listeners ---
    if (episodesContainer) {
        episodesContainer.addEventListener('click', (event) => {
            const episodeCard = event.target.closest('.episode-selector');
            if (episodeCard) {
                event.preventDefault();
                const episodePk = episodeCard.dataset.episodePk;

                highlightEpisode(episodeCard);
                displayTranslationOptions(episodePk); // Display options, don't preselect here
                currentSelectedTranslationId = null; // Reset selected translation on episode change

                if (mediaDescription) {
                    mediaDescription.style.display = 'block';
                }
            }
        });
    }

    if (translationSelectorPlaceholder) {
        translationSelectorPlaceholder.addEventListener('click', (event) => {
            const translationButton = event.target.closest('.translation-btn');
            if (translationButton) {
                event.preventDefault();
                const linkPk = translationButton.dataset.linkPk;
                currentSelectedTranslationId = translationButton.dataset.translationId; // Store selected ID

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
    restoreLastWatchedState();

}); // End DOMContentLoaded