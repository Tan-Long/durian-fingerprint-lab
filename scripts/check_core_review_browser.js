// Run using browser_run_code_unsafe filename. Port 8773 MUST use isolated test state.
async (page) => {
  const context = await page.context().browser().newContext();
  const probe = await context.newPage();
  const check = (value, message) => { if (!value) throw new Error(message); };
  const errors = [];
  probe.on('pageerror', error => errors.push(error.message));
  try {
    await probe.setViewportSize({width:1440,height:800});
    await probe.goto('http://127.0.0.1:8773/');
    await probe.locator('#caseView').waitFor({state:'visible'});
    const scale = await probe.evaluate(() => innerWidth / 1440);
    await probe.setViewportSize({width:Math.round(1440/scale),height:Math.round(800/scale)});
    check(await probe.title() === 'SoilTECH · Duyệt kết quả code', 'Core heading missing');
    check((await probe.locator('#codeNotice').textContent()).includes('KHÔNG phải nhận diện mã'), 'Known-sample diagnostic limits must be visible');
    check((await probe.locator('#codeNotice').textContent()).includes('CHƯA KHỚP'), 'Zero-inlier failure must be visible above photos');
    check(await probe.locator('#jumpPhotos').isVisible(), 'Real evidence needs photo navigation');
    check(await probe.locator('#gallery .query_photo').count() === 1, 'Query photo missing');
    check(await probe.locator('#gallery select').count() === 2, 'Both RGBD stream layer selectors required');
    check(await probe.locator('#gallery .match_overlay').count() === 2, 'Both camera correspondence overlays required');
    let layersDecoded=0;
    for(const selector of await probe.locator('#gallery select').all()){
      const options=await selector.locator('option').evaluateAll(items=>items.map(item=>item.value));
      check(options.length>=4,'RGB, depth, confidence and mask layers required');
      for(const value of options){await selector.selectOption(value);await selector.locator('xpath=ancestor::figure').locator('img').evaluate(node=>node.decode());layersDecoded++;}
      await selector.selectOption(options[0]);
    }
    for(const img of await probe.locator('#gallery img').all()){
      await img.scrollIntoViewIfNeeded();
      await img.evaluate(node=>node.decode());
    }
    await probe.locator('#gallery .match_overlay button').first().click();
    await probe.waitForFunction(()=>document.getElementById('largePhoto').naturalWidth>0);
    await probe.locator('#zoomIn').click();await probe.locator('#zoomIn').click();
    const zoom=await probe.locator('#photoViewport').evaluate(view=>{view.scrollTop=view.scrollHeight;view.scrollLeft=view.scrollWidth;return {top:view.scrollTop,left:view.scrollLeft};});
    check(zoom.top>0||zoom.left>0,'Zoomed matches must scroll');
    await probe.keyboard.press('Escape');
    await probe.locator('#photoDialog').waitFor({state:'hidden'});
    check(await probe.locator('#resultTables tbody tr').count() > 0, 'Result rows missing');
    await probe.locator('.queue').hover();
    await probe.evaluate(() => scrollTo(0,0));
    await probe.mouse.wheel(0,500);
    await probe.waitForFunction(() => scrollY > 0);
    check(await probe.evaluate(() => scrollY > 0), 'Document scroll is trapped');
    await probe.locator('#nextCase').click();
    check((await probe.locator('#caseTitle').textContent()).includes('Hộc'), 'Morphology case missing');
    check((await probe.locator('#resultTables').textContent()).includes('KHÔNG PHẢI DỰ ĐOÁN'), 'Reference values must not be presented as predictions');
    check((await probe.locator('#codeNotice').textContent()).includes('Chưa có mô hình'), 'Missing image predictor must be explicit');
    check(await probe.locator('#gallery .photo').count()===6,'Need full label card and five after-opening reference photos');
    for(const img of await probe.locator('#gallery img').all()){await img.scrollIntoViewIfNeeded();await img.evaluate(node=>node.decode());}
    const note = 'BROWSER TEST ONLY — phản hồi thử, không phải người dùng duyệt.';
    await probe.locator('#decision').selectOption('needs_changes');
    await probe.locator('#comment').fill(note);
    await probe.locator('#save').click();
    await probe.locator('#saveState').filter({hasText:'Đã lưu trên máy'}).waitFor();
    await probe.reload();
    await probe.locator('#caseView').waitFor({state:'visible'});
    check((await probe.locator('#history').textContent()).includes(note), 'Saved comment lost after reload');
    check(await probe.locator('#caseStatus').textContent() === 'Cần sửa', 'Saved decision lost');
    await probe.locator('#decision').selectOption('comment');
    await probe.locator('#comment').fill('BROWSER TEST ONLY — comment tiếp theo giữ kết luận trước.');
    await probe.locator('#save').click();
    await probe.locator('#saveState').filter({hasText:'Đã lưu trên máy'}).waitFor();
    check(await probe.locator('#caseStatus').textContent() === 'Cần sửa', 'Comment changed decision');
    await probe.locator('#nextCase').click();
    check((await probe.locator('#findings').textContent()).includes('Không có mã mẫu'), 'Failed dataset retrieval must remain visible');
    check(await probe.locator('#gallery img').count()===7,'Query and three exact frame/overlay pairs required');
    for(const img of await probe.locator('#gallery img').all()){await img.scrollIntoViewIfNeeded();await img.evaluate(node=>node.decode());}
    await probe.setViewportSize({width:Math.round(390/scale),height:Math.round(640/scale)});
    await probe.reload();
    await probe.locator('#caseView').waitFor({state:'visible'});
    check(await probe.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow');
    await probe.locator('#save').scrollIntoViewIfNeeded();
    check(await probe.locator('#save').isVisible(), 'Mobile save unreachable');
    check(errors.length === 0, errors.join('\n'));
    return {desktop:'OK',mobile:'OK',layersDecoded,referencePhotos:6,zoom,saveReload:'OK',commentPreservesDecision:'OK',errors,writes:'isolated test state only'};
  } finally { await context.close(); }
}
