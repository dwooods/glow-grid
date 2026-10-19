// Help dialog content. Kept out of index.html so page edits stay small. Classic script: fills #helpBody at load (load order is in index.html).
// Plain HTML inside a template literal: write \\ for a backslash, and avoid backticks and ${ in the text.
$('helpBody').innerHTML = `
          <p class="hint">Glow Grid is for drawing pixel art and checking what survives the Pi's brightness cap and gamma curve (the dashed outlines and the Panel check) before it goes near the panel. The Pi fits any image to the grid and plays it. How good it looks depends on what you give it.</p>
          <h3>Guide: build a sprite</h3>
          <figure class="help-fig">
            <svg viewBox="0 0 450 190" role="img" aria-label="The editor: the grid on the left; tools, colour, frames and move controls on the right, numbered like the steps">
              <g class="b"><rect x="10" y="10" width="136" height="136" rx="4"/></g>
              <g class="af" opacity=".85"><rect x="44" y="44" width="17" height="17"/><rect x="61" y="44" width="17" height="17"/><rect x="78" y="44" width="17" height="17"/><rect x="44" y="61" width="17" height="17"/><rect x="95" y="61" width="17" height="17"/><rect x="44" y="78" width="17" height="17"/><rect x="61" y="95" width="17" height="17"/><rect x="78" y="95" width="17" height="17"/><rect x="95" y="95" width="17" height="17"/></g>
              <text x="78" y="164" text-anchor="middle" class="d">the grid</text>
              <g class="b"><rect x="170" y="10" width="272" height="30" rx="6"/><rect x="170" y="52" width="272" height="30" rx="6"/><rect x="170" y="94" width="272" height="30" rx="6"/><rect x="170" y="136" width="272" height="30" rx="6"/></g>
              <text x="200" y="30">Paint · Fill · Erase · Pick</text>
              <text x="200" y="72">Colour wheel · Shade · Hex · Palette</text>
              <text x="200" y="114">Frames: [1] [2] [3]  + Duplicate</text>
              <text x="200" y="156">Move ↑←→↓ · All frames</text>
              <g class="af"><circle cx="186" cy="25" r="9"/><circle cx="186" cy="67" r="9"/><circle cx="186" cy="109" r="9"/><circle cx="186" cy="151" r="9"/></g>
              <g class="ink" text-anchor="middle"><text x="186" y="29">1</text><text x="186" y="71">2</text><text x="186" y="113">3</text><text x="186" y="155">4</text></g>
            </svg>
            <figcaption class="hint">The numbers match the steps below.</figcaption>
          </figure>
          <ol>
            <li><strong>Pick a tool.</strong> <em>Paint</em> colours a pixel (drag to keep going). <em>Fill</em> floods the connected pixels of one colour. <em>Erase</em> sets a pixel to black, which is off on the panel. <em>Pick</em> (or Alt+click while painting) copies the colour under the cursor and returns to Paint.</li>
            <li><strong>Pick a colour.</strong> Click the wheel (round = hue, outward = saturation), drag <em>Shade</em> to darken it, type a hex code, or tap a palette swatch. Colours already in your picture are under <em>In this picture</em>.</li>
            <li><strong>Draw the first frame.</strong> Undo and Redo are Ctrl+Z and Ctrl+Y. <em>Clear frame</em> blanks the current frame; <em>Start over</em> resets everything. Both can be undone.</li>
            <li><strong>Add frames.</strong> <em>+ Duplicate</em> copies the current frame (the quickest way to make motion: copy, then change a little). <em>+ Blank</em> adds an empty one. Up to 16 frames. Click a frame in the strip to edit it; <em>Delete frame</em> removes the current one. Closed the page by mistake? <em>Restore last session</em> appears after a reload.</li>
            <li><strong>Move.</strong> The arrows under <em>Move and layers</em>, or Shift+arrow keys, shift the current frame by one pixel. Duplicate, nudge, repeat: that makes a bounce or a slide.</li>
            <li><strong>Play.</strong> <em>Play</em> previews the loop; <em>FPS</em> (1 to 30) sets the speed. Then save it: see Guide: saving.</li>
          </ol>
          <p class="hint"><strong>Changing every frame at once.</strong> Tools and arrows act on the current frame only, unless you turn on <em>Edit all frames at once</em>. That is the way to repaint or move something every frame shares (a background, a body), and also to animate just one part:</p>
          <figure class="help-fig">
            <svg viewBox="0 0 420 110" role="img" aria-label="Three frames: the body is the same in each (the shared layer); only the arm changes">
              <g class="b"><rect x="10" y="10" width="80" height="80" rx="4"/><rect x="170" y="10" width="80" height="80" rx="4"/><rect x="330" y="10" width="80" height="80" rx="4"/></g>
              <g class="still"><rect x="34" y="30" width="32" height="40"/><rect x="194" y="30" width="32" height="40"/><rect x="354" y="30" width="32" height="40"/></g>
              <g class="af"><rect x="66" y="30" width="14" height="8"/><rect x="226" y="40" width="14" height="8"/><rect x="386" y="52" width="14" height="8"/></g>
              <g class="a"><path d="M96 50h68M256 50h68M158 44l6 6-6 6M318 44l6 6-6 6"/></g>
              <text x="50" y="106" text-anchor="middle" class="d">frame 1</text><text x="210" y="106" text-anchor="middle" class="d">frame 2</text><text x="370" y="106" text-anchor="middle" class="d">frame 3</text>
              <text x="130" y="72" text-anchor="middle" class="d">grey = shared</text>
            </svg>
          </figure>
          <ol>
            <li>Draw the whole character on one frame, then <em>+ Duplicate</em> it once per extra frame.</li>
            <li>Tick <em>Edit all frames at once</em> (it needs two or more frames). Whatever is identical in every frame becomes one shared layer; each frame keeps only what differs.</li>
            <li>The two buttons under it are greyed out until the box is ticked. <strong>All frames</strong> paints or moves the shared layer, so the change shows in every frame (recolour the body, shift the whole picture, change the background). <strong>This frame only</strong> changes just the current frame (the arm).</li>
            <li>To recolour something that differs in each frame, repaint it frame by frame. There is no shortcut yet.</li>
          </ol>
          <h3>Guide: Wi-Fi setup</h3>
          <figure class="help-fig">
            <svg viewBox="0 0 420 100" role="img" aria-label="Steps: save the network over USB, unplug USB and power the board, connect over Wi-Fi">
              <g class="b"><rect x="6" y="14" width="116" height="60" rx="8"/><rect x="152" y="14" width="116" height="60" rx="8"/><rect x="298" y="14" width="116" height="60" rx="8"/></g>
              <g class="a"><path d="M124 44h26M270 44h26"/><path d="M144 38l6 6-6 6M290 38l6 6-6 6"/></g>
              <text x="64" y="38" text-anchor="middle">1 USB</text><text x="64" y="56" text-anchor="middle" class="d">Save to board</text>
              <text x="210" y="38" text-anchor="middle">2 Unplug USB</text><text x="210" y="56" text-anchor="middle" class="d">power the board</text>
              <text x="356" y="38" text-anchor="middle">3 Wi-Fi</text><text x="356" y="56" text-anchor="middle" class="d">Connect over Wi-Fi</text>
              <text x="210" y="94" text-anchor="middle" class="d">the board joins your 2.4 GHz network by itself</text>
            </svg>
          </figure>
          <p class="hint"><strong>First time, with a computer</strong> (Chrome or Edge, board on USB):</p>
          <ol>
            <li>In the Board card press <em>Connect over USB</em>. Close the Arduino Serial Monitor first.</li>
            <li>Press <strong>Network</strong> at the top, then <em>Scan for networks</em> (the panel pauses a few seconds). Pick yours, or type its name. The board hears <strong>2.4 GHz only</strong>: a 5 GHz-only network never shows.</li>
            <li>Type the password (8 to 63 characters; empty for an open network) and press <em>Save to board</em>. The dialog says "Joined" and shows the board's address.</li>
            <li><strong>Unplug USB and power the board</strong> from its supply. It joins the saved network on its own.</li>
            <li>Open <strong>Network</strong>, check the address (<code>glowgrid.local</code>, or the IP if your device cannot find that name) and press <em>Connect over Wi-Fi</em>. Chrome may ask once to allow access to devices on your network: choose <em>Allow</em>.</li>
          </ol>
          <p class="hint"><strong>Saved network.</strong> With the board on USB, the <em>Saved network</em> section shows the network the board has stored and its address. <em>Forget saved network</em> removes it; the board then opens GlowGrid-Setup after its next power-up.</p>
          <p class="hint"><strong>Changing the network, or no computer.</strong> The board opens its own network by itself when it has no saved network, and again if a network you just saved does not join. The network is named <code>GlowGrid-Setup-</code> and four digits, and it is protected with WPA3. The board makes up a new name and a new 8-digit password every time and <strong>shows the password on the panel</strong>, so you have to be at the board to join. Nothing is printed on the box or stored. To open it on purpose, press <em>Change the board's Wi-Fi…</em> while connected over Wi-Fi, hold the On/off button for 5 seconds, or <em>Forget saved network</em> and power-cycle. A saved network that is merely slow to join after a power cut does <em>not</em> open it: the board keeps trying. WPA3 needs a phone from roughly 2018 or later; an older phone cannot join, so use USB then.</p>
          <ol>
            <li>Look at the panel: it shows 8 digits in two rows of four, and a blue bar along the bottom that shrinks as the 5 minutes run out. On your phone, join the Wi-Fi network <code>GlowGrid-Setup-</code> plus four digits, and type the 8 digits as the password. The setup page opens; if it does not, go to <code>http://192.168.4.1/</code>.</li>
            <li>Pick your network, type the password and press Save. The page counts down a few seconds while the board joins.</li>
            <li>The setup network closes after 5 minutes. A wrong password or name brings it back, so you can try again, with a new name and new digits.</li>
            <li><strong>Forget the setup network on your phone</strong> (Wi-Fi settings, the <code>GlowGrid-Setup-…</code> entry, <em>Forget This Network</em>). The name and the password change every time, so a phone that saved an earlier one cannot rejoin it: if a join fails with "incorrect password", forget every old <code>GlowGrid-Setup-…</code> entry and join the one with the digits now showing on the panel. Saved entries do no harm, but they pile up.</li>
          </ol>
          <p class="hint"><strong>iPhone and Safari</strong> cannot reach the board from this https page. Open the board's own address in Safari instead, <code>http://glowgrid.local/</code> (or <code>http://</code> and its IP): the board serves this same editor. Only USB and the Wi-Fi setup need a computer.</p>
          <h3>Guide: saving, and why</h3>
          <figure class="help-fig">
            <svg viewBox="0 0 420 170" role="img" aria-label="One drawing exports three ways: Raspberry Pi PNG, enlarged PNG to view or share, and a .gg file for the ESP32-C3">
              <g class="b"><rect x="6" y="56" width="90" height="48" rx="8"/><rect x="190" y="8" width="224" height="40" rx="8"/><rect x="190" y="64" width="224" height="40" rx="8"/><rect x="190" y="120" width="224" height="40" rx="8"/></g>
              <text x="51" y="84" text-anchor="middle">Drawing</text><text x="51" y="98" text-anchor="middle" class="d">File ▸ Export</text>
              <g class="a"><path d="M98 80C140 80 140 28 186 28M98 80H186M98 80C140 80 140 140 186 140"/></g>
              <text x="200" y="26">Raspberry Pi</text><text x="200" y="41" class="d">PNG, 1 pixel per LED</text>
              <text x="200" y="82">View or share</text><text x="200" y="97" class="d">PNG, enlarged ×8/×16/×32</text>
              <text x="200" y="138">ESP32-C3</text><text x="200" y="153" class="d">.gg file, 16×16, up to 16 frames</text>
            </svg>
          </figure>
          <p class="hint">Open <strong>File ▸ Export…</strong>, type a <em>Name</em>, choose <em>Export for</em> and press <em>Save</em>. One frame saves a still; two or more save an animation.</p>
          <ul>
            <li><strong>Raspberry Pi:</strong> a PNG with exactly one pixel per LED, so the Pi plays it pixel for pixel. Brightness, gamma, grid size, frame count and fps are stored inside, so the file name can be anything. Copy it to <code>~/glow-grid/images/</code> (see <em>Getting a picture onto the panel</em>). Use this as your keeper file too: <strong>File ▸ Import image</strong> brings it back as separate frames.</li>
            <li><strong>View or share (PNG):</strong> an enlarged, sharp copy (<code>_x16</code> in the name) for looking at, a blog or a message. Pick the <em>Scale</em>. Do not put it on the Pi: an enlarged animation plays there as one squashed still.</li>
            <li><strong>ESP32-C3 (.gg):</strong> a small file for the C3 player, 16×16 and up to 16 frames only. Pixels stay as drawn; the board applies the wiring, gamma and brightness cap itself. Reopen one with <strong>File ▸ Open .gg sprite</strong>.</li>
            <li><strong>Straight to the board:</strong> with the Board card connected (USB or Wi-Fi), <em>Send to board</em> stores the current drawing under the <em>Name</em> beside it and plays it, with no file to copy. A new Name adds a sprite; a Name already on the board replaces it (you are asked first), so to save a changed copy, change the Name before Send. <em>Load</em> in the board's list brings a stored sprite back into the editor.</li>
            <li><strong>Where it goes:</strong> Chrome and Edge ask where to save; other browsers put the file in Downloads.</li>
          </ul>
          <h3>Guide: make a sprite with AI</h3>
          <p class="hint">An AI that can run code and hand back files (Claude with file tools, Claude Code, ChatGPT with its code tool) can draw a new sprite for you. Paste the prompt below. It asks about the grid size, the picture, the background, brightness, gamma and your power supply, then returns a PNG that loads here. It makes a new sprite; it is not for changing the one in the editor.</p>
          <p class="btn-row"><button type="button" class="btn btn-quiet" id="aiCopy">Copy prompt</button><span class="hint" id="aiCopied" role="status"></span></p>
          <pre class="ai-prompt" id="aiPrompt" tabindex="0">I want you to make an original pixel-art sprite for a WS2812 LED panel and give it to me as a PNG file that I load into Glow Grid (dwooods.github.io/glow-grid). Design something original: do not copy an existing character, logo or artwork.

First ask me these questions, all in one message, and wait for my answers before you draw anything:
1. Grid size, columns by rows. The default is 16 x 16, but it could be 8 x 8, 8 x 32 or something else (up to 64 x 64).
2. What is it? The subject, the mood, the style, and any colors I want or want to avoid.
3. Still or animated? If animated: what moves, how many frames (1 to 16) and the speed in frames per second (1 to 30, default 6). Should it loop smoothly?
4. Background: black, which means the LEDs are off (recommended: it looks best and uses no power), or a color?
5. LED brightness (default 0.3; the Pi caps it at 0.4), gamma (default 2.2) and my power supply in amps (default 6)?
6. A file name (letters, digits, - and _ only).

Then build it:
- Draw each frame as text, one character per pixel plus a palette, in a Python script, and write the PNG with Pillow. Show me the palette and the frames as text so I can review them.
- The file is one RGB PNG with all frames side by side in a single row. Each frame is exactly columns x rows pixels, so the image is (frames x columns) wide and rows tall. No scaling, no antialiasing, no transparency. Name it &lt;name&gt;_&lt;fps&gt;fps.png for an animation (for example bunny_8fps.png) or &lt;name&gt;.png for a still.
- Also store my light settings in the PNG as a text chunk named glow-grid holding compact JSON, keys in this order: brightness, gamma, cols, rows, and for animations frames and fps. Example: {"brightness":0.3,"gamma":2.2,"cols":16,"rows":16,"frames":8,"fps":8}. With Pillow: build a PngInfo, call add_text("glow-grid", json.dumps(meta, separators=(",", ":"))) and pass it as pnginfo= to save().
- Colors for LEDs: pure black (0,0,0) is off. Use saturated, bright colors. Keep every lit pixel's brightest channel at 80 or more out of 255, because at my brightness and gamma anything darker shows as a faint smudge or vanishes. Shade with a lighter and a darker version of a color, never a muddy one. Avoid dark brown, navy and gray: they wash out.
- Power: estimate each frame's draw in amps. For every pixel, black ones included, compute level = 255 x brightness x (value / 255) ^ gamma for each of R, G and B. The pixel draws (levelR + levelG + levelB) / 255 x 20 mA plus 0.6 mA. Add up all pixels in the frame. Keep my brightest frame under 80% of my supply's amps and tell me the number; if it is over, reduce the lit area or the colors.
- Animation: keep the subject anchored, change only a little between frames, and make the last frame lead back into the first. Every frame must be complete (no "same as before").
- Check your work: save an enlarged preview (each pixel drawn 16 x 16 on a dark gray background, frames in a grid), look at it, and fix anything that is unclear at that size.
- Finish by giving me the PNG and a summary: grid size to set, frame count, fps, brightness, gamma, and the estimated peak draw against my supply.</pre>
          <ol>
            <li><strong>Answer its questions.</strong> Say the grid size you will use: <em>Cols</em> by <em>Rows</em> (a tall 8 by 32 panel is 8 columns, 32 rows).</li>
            <li><strong>Set the same size here first.</strong> Under <em>Panel settings</em>, type the <em>Cols</em> and <em>Rows</em> and press <em>Apply size</em>.</li>
            <li><strong>Load it.</strong> <em>File ▸ Import image…</em> and pick the PNG. All the frames, the speed, the brightness and the gamma come in with it.</li>
            <li><strong>If the crop window opens instead,</strong> the grid size here does not match the PNG, or the file lost its frame count and name tag. Set the size and import again.</li>
          </ol>
          <p class="hint">The AI cannot see your panel, so check the result: Play, look for the dashed outlines (Panel Check) and read the amps under Panel settings. Ask it for another version, or touch it up here.</p>
          <h3>Works well</h3>
          <ul>
            <li><strong>Pixel art at or near grid size</strong> (drawn here, in Piskel, or the examples) comes out pixel-perfect.</li>
            <li><strong>Photos and large images:</strong> anything more than 2× the grid is averaged per cell, so photos come out smooth instead of noisy.</li>
            <li><strong>Animations:</strong> an animated GIF, or a sprite sheet (frames side by side, as tall as the grid) named with the speed, <code>walk_8fps.png</code>, or <code>_sheet</code>.</li>
            <li><strong>Transparency</strong> becomes "off" LEDs.</li>
            <li><strong>Non-square images</strong> are centered and fitted without stretching.</li>
          </ul>
          <h3>Animation files: sheet, fps and names</h3>
          <ul>
            <li><strong>Sprite sheet</strong> = one PNG with all frames side by side, like a film strip. 4 frames on a 16×16 grid make a 64×16 image. <strong>fps</strong> = how fast the frames play (4 fps = a quarter second per frame). The sheet says what the file is; fps says how fast to play it.</li>
            <li><strong>Saved from here:</strong> the frame count and fps are stored inside the PNG, so you can rename the file to anything (<code>ghost.png</code>). Brightness and gamma are stored there too, and the Pi menu shows all of them next to the file name.</li>
            <li><strong>From other tools</strong> (Piskel, hand-made strips): the name decides. <code>walk_4fps.png</code> plays at 4 fps (it marks a sheet and sets the speed). <code>walk_sheet.png</code> plays at the default 6 fps. A plain <code>walk.png</code> plays as one squashed still.</li>
            <li><strong>The Pi's speed order:</strong> the number you type, then the fps in the PNG, then <code>_Nfps</code> in the name, then 6.</li>
            <li><strong>Can lose the stored data:</strong> re-saving in another editor, and scaled exports (<code>_x8</code>, which play as stills). Copying with <code>scp</code> keeps it. Avoid spaces in names.</li>
          </ul>
          <h3>Edit all frames: move and shared layer</h3>
          <ul>
            <li><strong>Move:</strong> the arrows in <em>Move and layers</em> (or Shift+arrow keys) shift this frame one pixel. Duplicate a frame, nudge it, repeat: that makes a bob or a slide.</li>
            <li><strong>Edit all frames at once:</strong> draw the whole character and duplicate it for each frame, then tick the box. Everything identical in all frames becomes one shared layer, leaving each frame with only what changes (hand, legs, eyes, mouth). Choose <em>All frames</em> to paint or move the shared layer for every frame at once, or <em>This frame only</em> to paint those changing bits per frame. Black on a frame is see-through. Untick to join the layers back.</li>
            <li><strong>Saved files</strong> always combine the layers, so the Pi and the sprite sheet need nothing new.</li>
          </ul>
          <h3>Drawing tools</h3>
          <ul>
            <li><strong>Keyboard drawing:</strong> Tab to the grid, move the cursor with the arrow keys, and press Space or Enter to apply the current tool (Paint, Fill, Erase or Pick) at the cursor. Hold Space while moving to keep painting. Shift+arrows still move the whole picture. Escape leaves the grid.</li>
            <li><strong>Undo and redo:</strong> Ctrl+Z and Ctrl+Y, or the buttons. Clear frame, Delete frame and Start over can all be undone.</li>
            <li><strong>Shade</strong> (the slider beside the color wheel) sets how light or dark the paint color is, from black at 0 to the full color at 100. It only changes the color you paint with. It is not the LED brightness in Panel settings, which sets how bright the panel runs.</li>
            <li><strong>Erase</strong> sets a pixel to black, which is "off" on the panel. <strong>Pick</strong> (or Alt+click while painting) takes the color under the cursor and goes back to Paint.</li>
            <li><strong>Panel check</strong> (under Panel settings) shows dashed outlines on the grid for pixels you may want to fix, and a summary of how many. <em>Yellow</em> is almost black: the LED lights it at only 1 to 3 out of 255, so a "black" background drawn as #010101 glows as a faint smudge; fill it with #000000 to turn it off. <em>Purple</em> is a color shift: the hue changes at this brightness and gamma. Untick the box to hide the outlines. The estimated current draw and its meter sit beside the settings.</li>
          </ul>
          <h3>Drawing on a phone</h3>
          <ul>
            <li><strong>The grid fills the width.</strong> At the bottom is a dock that stays put: Paint, Fill, Erase and Pick, your color (tap it to jump to the color wheel), and the palette (swipe it sideways; colors already in your picture come first). Under the grid is a row with Play, Undo, Redo, <strong>+</strong> to duplicate a frame and <strong>More</strong>, and your frames below it.</li>
            <li><strong>Swipe up</strong> (anywhere except on the grid, where a finger paints) to scroll the rest of the controls into view: frame speed, blank, delete and start over, Move and layers, the color wheel and hex, Clear frame and the Panel settings. <strong>More</strong> jumps straight to them. Turn the phone sideways and the page goes back to the plain scrolling layout.</li>
            <li><strong>The magnifier:</strong> while a finger or pen is painting or erasing, a close-up of the pixels around it floats beside your finger, with the pixel you are on outlined. It appears only for touch and pen, never for a mouse.</li>
          </ul>
          <h3>Getting a picture onto the panel</h3>
          <p class="hint"><strong>File ▸ Import image</strong> loads everything: a sprite sheet or single frame saved from here comes back as separate frames; any other picture opens a crop-and-zoom editor. Tick <strong>Exact pixels</strong> for pixel art, or leave it off for photos. Both can remove the background. On a phone the picker offers the camera too.</p>
          <ul>
            <li><strong>Raspberry Pi</strong> makes one PNG with one pixel per LED. One frame saves a still, two or more save a sprite sheet. Brightness, gamma, grid size and (for an animation) frame count and fps go inside the file, so the name can stay plain.</li>
            <li><strong>Copy it to the Pi</strong> from your PC, then run <code>glow-grid</code>, press <code>r</code> to rescan and pick the file. In PowerShell: <code>scp "$HOME\\Downloads\\sprite.png" user@raspberrypi.local:~/glow-grid/images/</code> (change the file name and login to match yours).</li>
            <li><strong>View or share (PNG)</strong> saves a sharp, enlarged copy (named <code>_x16</code> etc.) to look at or send to someone. Don't copy it to the Pi: an enlarged animation would play as one squashed still.</li>
            <li><strong>ESP32-C3</strong> saves a small <code>.gg</code> sprite file for the C3 player (16×16 only, up to 16 frames: the panel is for simple loops). The pixels stay as drawn; the board applies the wiring, gamma and the brightness cap. Put it on the board from your PC: <code>python c3/tools/gg_tool.py put sprite.gg</code> (the same name replaces the old sprite).</li>
            <li><strong>Board card</strong> (board on USB in Chrome or Edge, or on Wi-Fi in any browser): <em>Connect over USB</em> picks the USB port, or <em>Connect over Wi-Fi</em> reaches a board on your network (its address is under the <strong>Network</strong> button at the top). Then <em>Send to board</em> stores the current drawing under the <em>Name</em> beside it and plays it; the list shows what is on the board with Load, Play and Delete for each, and each name also shows its frames, speed, brightness and gamma in brackets (<em>Load</em> reads the sprite back into the editor grid, with its frames, speed, brightness and gamma, so you can change it and Send it again under the same name to replace it, or under a new Name to keep both; it asks before replacing a drawing; <strong>File ▸ Open .gg sprite</strong> does the same from a file on your computer), and <em>Lights off</em> blanks the LEDs (and keeps them dark across a power cycle until <em>Lights on</em>). The Name field is the same one as in Export; sending a name that is already on the board asks before replacing it, and a blank drawing is refused. <em>Rotate</em> makes the board move to the next stored sprite on its own (every 10 seconds up to once a day); each sprite keeps playing for the whole interval, and the board remembers the setting after a power cycle. It picks a random sprite each time, never the one already playing (a board with old software goes through the list in order; update it to get random order). <em>Brightness</em> plays every stored sprite at one brightness (0.1 to 0.4) without sending them again, or <em>each sprite's own</em> uses what is saved in each file; the board remembers it after a power cycle. <em>Schedule</em>: tick it and type two 24-hour times (like 07:00 and 20:00) and the panel switches itself off at the second and on at the first, every day, in Los Angeles time. A line under it says what the two times mean, including overnight (an off time earlier than the on time keeps the lights on through the night). The board learns the time over Wi-Fi after it joins, so a board only on USB has no time and the schedule waits; a line appears under the controls while the board has no time yet. Pressing Lights on or off by hand holds until the next scheduled change, and when you save a schedule the panel goes straight to the state the window calls for. The list shows five sprites a page; <em>Prev</em> and <em>Next</em> move through the rest. <em>Add examples</em> stores the original example sprites from the repo on the board (it never replaces a sprite that is already there); <em>Remove examples</em> deletes them again, but keeps any you changed or replaced under an example's name (it needs newer board software on an old board; Connect shows the board's software version). Close the Arduino Serial Monitor first. Where the card works over USB: Chrome, Edge or another Chromium browser on Windows, macOS or Linux, with the board plugged into that computer. Where it does not (Connect over USB is greyed out and says so): Safari on a Mac, Firefox, and every browser on an iPhone or iPad, because none of them can open a USB port. Wi-Fi does not need a USB port, so use that there (on an iPhone, from the editor the board serves at its own address), or <em>Export for ESP32-C3</em> and <code>gg_tool.py</code> from a computer. Android Chrome is untested.</li>
            <li><strong>Network</strong> (the button at the top): with the board on USB, press <em>Scan for networks</em> (the panel pauses a few seconds), pick yours from the list and type its password, or type the name yourself (hidden networks are not listed, and a 5 GHz-only network never shows because the board hears 2.4 GHz only), then press <em>Save to board</em>; the board stores them, joins (2.4 GHz networks only) and the dialog shows its address, which the Board card also keeps next to USB. Unplug USB, power the board, and press <em>Connect over Wi-Fi</em> (the address is <code>glowgrid.local</code>, or the IP address if your device does not resolve that). Chrome on a computer may ask once whether this page may reach devices on your network: choose Allow. Safari on an iPhone refuses to let this https page call the board, so on a phone open the board's own address instead, <code>http://glowgrid.local/</code> or <code>http://</code> and its IP address: the board serves this same editor itself, it connects on its own, and everything but USB and the Wi-Fi setup works there. Without a computer: the board opens its own setup network, <code>GlowGrid-Setup</code> by itself when it has no saved network, or when a network you just saved does not join; join it from your phone, the setup page opens, pick your network, type the password and Save. That setup network is named <code>GlowGrid-Setup-</code> and four digits, uses WPA3, and has a new name and a new 8-digit password every time; the password is shown on the board's panel, not on a label. (A board with old software uses a stored setup key instead; <em>Show setup key</em> displays it while the board is on USB.) With the board on Wi-Fi, <em>Change the board's Wi-Fi</em> in this dialog does the same on request: stand where you can see the panel. Forget the setup network on your phone afterwards, or when a join says "incorrect password": the name and password change every time, so an old saved entry never works again. A saved network that is slow to join after a power cut no longer opens the setup network; hold the On/off button for 5 seconds, or use USB, if the network really changed. The setup network closes after 5 minutes, and the board then goes back to its saved network. Anyone on your home network can still list, send and delete sprites, and can ask the board to open its setup network (it then leaves your Wi-Fi for up to 5 minutes, but cannot be joined without seeing the panel); there is no password on that side yet, but a web page on another site cannot: the board refuses requests that do not come from this editor, its own page or your own computer, and the setup network can only be joined with the digits shown on the panel. Tried against the real board: Chrome on Windows, in a tab and as the installed app (Chrome shows \"Not secure\" on the page because the board speaks plain http). iPhone Safari: the hosted https editor cannot reach the board, but the editor served by the board itself loads, connects, lists the sprites and plays them. Not tried: Firefox and Android.</li>
          </ul>
          <h3 id="helpSettings">Panel settings</h3>
          <ul>
          <li><strong>LED brightness:</strong> how bright the LEDs run, from 0.05 to 1. The Pi caps it at <code>MAX_BRIGHTNESS</code> (0.4 by default, about 6 A for full white), so anything higher plays at 0.4.</li>
          <li><strong>Gamma:</strong> corrects for how eyes see light. LEDs get brighter in even steps, but we notice dark shades more than bright ones, so without correction mid-tones look washed out. Gamma darkens the middle of the range to compensate. 2.2 is the usual value. Raise it for more contrast and deeper colors (very dark shades can drop to off), lower it toward 1 for a flatter, brighter look.</li>
          <li><strong>PSU amps:</strong> your power supply's rating. It only sets the limit on the Peak meter under the grid.</li>
          <li><strong>Cols and Rows:</strong> the panel's width and height in LEDs. The Pi program is built for 16×16. Saved files record the grid size, and the Pi menu flags a file made for a different size instead of squashing it silently. Making the grid smaller crops every frame; Undo reverts.</li>
          <li>Saved PNGs remember brightness and gamma, and <code>play.py</code> on the Pi uses them for that image, so the panel matches what you see here.</li>
          <li>The Panel check uses the same rounding and "keep non-black pixels lit" rule as the Pi, so its warnings match what the panel will do. The grid itself shows your colors as drawn, not as the LEDs will glow.</li>
        </ul>
          <h3>Watch out for</h3>
          <ol>
            <li><strong>Mid-size pixel art</strong> (between 1× and 2× the grid, e.g. a 24×24 sprite) keeps exact pixels, so some detail is dropped. Draw at grid size, or at an exact 2×, 3×… upscale.</li>
            <li><strong>Sprite sheets from other tools</strong> play as one squashed still unless the name has <code>_8fps</code> or <code>_sheet</code>. Sheets saved from here carry their frame count and speed inside the PNG, so renaming them is safe.</li>
            <li><strong>Wiring:</strong> until the probe settings are set and confirmed on the Pi (<code>glow-grid probe</code>, <code>glow-grid probe check</code>, then <code>k</code> in the menu), images may look scrambled; the menu warns you.</li>
            <li><strong>Near-black and dark colors:</strong> near-black isn't off, and dark shades can vanish. The Panel check outlines both.</li>
          </ol>
`;

// Copy button for the AI prompt (the text is also selectable, for browsers that block the clipboard)
$('aiCopy').addEventListener('click', async () => {
  const text = $('aiPrompt').textContent, note = $('aiCopied');
  try { await navigator.clipboard.writeText(text); note.textContent = 'Copied.'; }
  catch (e) {
    const r = document.createRange(); r.selectNodeContents($('aiPrompt'));
    const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
    note.textContent = 'Selected. Press Ctrl+C (Cmd+C on a Mac) to copy.';
  }
});

// Make the help easier to scan: each section becomes a fold (the first one open) and a row of chips at the top jumps to any of them.
// The text above is untouched; the h3s stay (inside the fold's summary), so anything that reads them still works.
(function () {
  const body = $('helpBody');
  const short = { 'Guide: build a sprite': 'Guide: draw', 'Guide: Wi-Fi setup': 'Guide: Wi-Fi', 'Guide: saving, and why': 'Guide: saving', 'Guide: make a sprite with AI': 'Guide: AI', 'Works well': 'Works well', 'Animation files: sheet, fps and names': 'Animation files', 'Edit all frames: move and shared layer': 'All frames',
    'Drawing tools': 'Drawing', 'Drawing on a phone': 'Phone', 'Getting a picture onto the panel': 'To the panel', 'Watch out for': 'Watch out' };
  const chips = document.createElement('nav');
  chips.className = 'help-chips'; chips.setAttribute('aria-label', 'Help sections');
  const folds = [];
  Array.from(body.querySelectorAll(':scope > h3')).forEach((h, i) => {
    const d = document.createElement('details'), s = document.createElement('summary');
    d.className = 'help-sec'; d.open = i === 0;
    h.replaceWith(d); s.appendChild(h); d.appendChild(s);
    while (d.nextElementSibling && d.nextElementSibling.tagName !== 'H3') d.appendChild(d.nextElementSibling);
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'btn btn-quiet help-chip'; b.textContent = short[h.textContent] || h.textContent;
    b.addEventListener('click', () => {
      d.open = true;
      d.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    });
    chips.appendChild(b); folds.push(d);
  });
  if (folds.length) body.insertBefore(chips, folds[0]);
})();
