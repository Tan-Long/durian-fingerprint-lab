// Browser tool check: run browser_run_code_unsafe with this file as filename.
// Uses an isolated tab on the local review host. No review writes or source edits.
async (page) => {
  const context = await page.context().browser().newContext();
  const probe = await context.newPage();
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  try {
    await probe.setViewportSize({ width: 1440, height: 800 });
    await probe.goto('http://127.0.0.1:8765/');
    await probe.locator('#caseView').waitFor({ state: 'visible' });
    // Respect the user's browser zoom without changing their browser settings.
    const browserScale = await probe.evaluate(() => innerWidth / 1440);
    await probe.setViewportSize({width:Math.round(1440/browserScale),height:Math.round(800/browserScale)});
    await probe.locator('#factsTitle').click();
    await probe.locator('.queue').hover();
    await probe.mouse.wheel(0, 500);
    await probe.waitForTimeout(250);
    const pageScroll = await probe.evaluate(() => scrollY);
    check(pageScroll > 0, 'Wheel over the sidebar must scroll the main document, not trap it');
    check(await probe.locator('#zoomIn').count() === 1, 'Photo viewer needs an explicit zoom control');
    await probe.locator('#gallery button').first().click();
    await probe.waitForFunction(() => document.getElementById('largePhoto').naturalWidth > 0);
    await probe.locator('#zoomIn').click();
    await probe.locator('#zoomIn').click();
    const metrics = await probe.locator('#photoViewport').evaluate(view => {
      view.scrollTop = view.scrollHeight;
      view.scrollLeft = view.scrollWidth;
      return { top: view.scrollTop, left: view.scrollLeft, height: view.clientHeight, total: view.scrollHeight };
    });
    check(metrics.total > metrics.height && metrics.top > 0, 'Zoomed photo bottom must be reachable by scrolling');
    await probe.locator('#fitPhoto').click();
    const fitted = await probe.locator('#photoViewport').evaluate(view => ({ top:view.scrollTop, total:view.scrollHeight, height:view.clientHeight }));
    check(fitted.top === 0 && fitted.total <= fitted.height + 1, 'Fit must restore the whole image without clipping');
    await probe.keyboard.press('Escape');
    check(!await probe.locator('#photoDialog').evaluate(dialog => dialog.open), 'Escape must close the photo');
    const pack = await (await probe.request.get('http://127.0.0.1:8765/api/review')).json();
    const sample = pack.cases.find(item => item.id === 'counts-N2V13C3');
    await probe.locator('#search').fill('N2V13C3');
    await probe.locator('.case-button').filter({hasText:sample.title}).click();
    const chambers = sample.media.filter(photo => photo.kind === 'chamber_photo');
    check(await probe.locator('#gallery .photo').count() === chambers.length, 'Every candidate chamber image must be rendered');
    check(await probe.locator('#otherGallery .photo').count() === sample.media.length - chambers.length, 'Exterior photos must stay separate');
    await probe.locator('#gallery button').first().click();
    await probe.locator('#nextPhoto').click();
    check(await probe.locator('#photoPosition').textContent() === `2 / ${chambers.length}`, 'Next must navigate the complete photo set');
    check(await probe.locator('#photoTitle').textContent() === chambers[1].label, 'Next must show the matching image');
    await probe.locator('#previousPhoto').click();
    check(await probe.locator('#photoPosition').textContent() === `1 / ${chambers.length}`, 'Previous must return to the first image');
    await probe.keyboard.press('Escape');
    await probe.locator('#openArchive').click();
    const archiveCount = pack.cases.find(item => item.id === 'chamber-archive').media.length;
    check(await probe.locator('#gallery .photo').count() === archiveCount && archiveCount === 427, 'All 427 original chamber images must be available, including unassigned ones');
    check((await probe.locator('#photosTitle').textContent()).includes('bảng kê hộc'), 'Archive must not claim every image depicts an opened locule');
    await probe.locator('.case-button').filter({hasText:sample.title}).click();
    await probe.setViewportSize({ width: Math.round(390/browserScale), height: Math.round(640/browserScale) });
    await probe.reload();
    await probe.locator('#caseView').waitFor({ state: 'visible' });
    check(!await probe.evaluate(() => document.documentElement.scrollWidth > innerWidth), 'Mobile page must fit horizontally');
    await probe.locator('#gallery button').first().click();
    await probe.waitForFunction(() => document.getElementById('largePhoto').naturalWidth > 0);
    await probe.locator('#zoomIn').click();
    const mobile = await probe.locator('#photoViewport').evaluate(view => {view.scrollTop=view.scrollHeight;return {top:view.scrollTop,height:view.clientHeight,total:view.scrollHeight};});
    check(mobile.height > 0 && mobile.top > 0, 'Mobile zoom must retain a scrollable photo area');
    return { pageScroll, zoomed: metrics, fitted, mobile, candidateImages:chambers.length, archiveImages:archiveCount, writes: 0 };
  } finally { await context.close(); }
}
