// Help dialog content. Kept out of index.html so page edits stay small. Classic script: fills #helpBody at load (load order is in index.html).
// Plain HTML inside a template literal: write \\ for a backslash, and avoid backticks and ${ in the text.
$('helpBody').innerHTML = `
          <p class="hint">Glow Grid is for drawing pixel art and checking what survives the Pi's brightness cap and gamma curve (the dashed outlines and the Panel check) before it goes near the panel. The Pi fits any image to the grid and plays it. How good it looks depends on what you give it.</p>
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
          <h3>Animating one part: move and still part</h3>
          <ul>
            <li><strong>Move:</strong> the arrows in <em>Move and layers</em> (or Shift+arrow keys) shift this frame one pixel. Duplicate a frame, nudge it, repeat: that makes a bob or a slide.</li>
            <li><strong>Animate one part only:</strong> draw the whole character and duplicate it for each frame, then tick the box. Everything identical in all frames becomes the still part, leaving each frame with only what changes (hand, legs, eyes, mouth). Paint just those bits per frame. Black on a frame is see-through. Untick to join it back.</li>
            <li><strong>Saved files</strong> always combine the layers, so the Pi and the sprite sheet need nothing new.</li>
          </ul>
          <h3>Drawing tools</h3>
          <ul>
            <li><strong>Keyboard drawing:</strong> Tab to the grid, move the cursor with the arrow keys, and press Space or Enter to apply the current tool (Paint, Fill, Erase or Pick) at the cursor. Hold Space while moving to keep painting. Shift+arrows still move the whole picture. Escape leaves the grid.</li>
            <li><strong>Undo and redo:</strong> Ctrl+Z and Ctrl+Y, or the buttons. Clear frame, Delete frame and Start over can all be undone.</li>
            <li><strong>Shade</strong> (the slider beside the color wheel) sets how light or dark the paint color is, from black at 0 to the full color at 100. It only changes the color you paint with. It is not the LED brightness in Panel settings, which sets how bright the panel runs.</li>
            <li><strong>Erase</strong> sets a pixel to black, which is "off" on the panel. <strong>Pick</strong> (or Alt+click while painting) takes the color under the cursor and goes back to Paint.</li>
            <li><strong>Panel check</strong> (under Panel settings) shows the estimated current draw and how many pixels are barely lit or will shift color. Its one-line summary shows a warning color when anything is flagged.</li>
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
            <li><strong>ESP32-C3</strong> saves a small <code>.gg</code> sprite file for the C3 player (16×16 only, up to 64 frames). The pixels stay as drawn; the board applies the wiring, gamma and the brightness cap. Put it on the board from your PC: <code>python c3/tools/gg_tool.py put sprite.gg</code> (the same name replaces the old sprite).</li>
            <li><strong>Board card</strong> (Chrome or Edge on a computer, board on USB): <em>Connect board</em> picks the port, then <em>Send to board</em> stores the current drawing under the Export name and plays it; the list shows what is on the board with Play and Delete for each, and <em>Lights off</em> blanks the LEDs (and keeps them dark across a power cycle until <em>Lights on</em>). The card says which name Send will use; the same name replaces, after asking, and a blank drawing is refused. Close the Arduino Serial Monitor first. Phones cannot open a USB port; Wi-Fi is the next step for them.</li>
          </ul>
          <h3>Watch out for</h3>
          <ol>
            <li><strong>Mid-size pixel art</strong> (between 1× and 2× the grid, e.g. a 24×24 sprite) keeps exact pixels, so some detail is dropped. Draw at grid size, or at an exact 2×, 3×… upscale.</li>
            <li><strong>Sprite sheets from other tools</strong> play as one squashed still unless the name has <code>_8fps</code> or <code>_sheet</code>. Sheets saved from here carry their frame count and speed inside the PNG, so renaming them is safe.</li>
            <li><strong>Wiring:</strong> until the probe settings are set and confirmed on the Pi (<code>glow-grid probe</code>, <code>glow-grid probe check</code>, then <code>k</code> in the menu), images may look scrambled; the menu warns you.</li>
            <li><strong>Near-black and dark colors:</strong> near-black isn't off, and dark shades can vanish. The Panel check outlines both.</li>
          </ol>
`;
