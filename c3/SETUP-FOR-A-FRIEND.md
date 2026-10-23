# Setting up your Glow Grid board

One-time setup, about five minutes. You need a computer (Windows, Mac or Linux) with **Chrome or Edge**, the board, and a USB-C cable that carries data (some charging cables do not). Safari and Firefox cannot do this step. A phone cannot either, because it cannot open a USB port. **No Chrome or Edge, or only a phone or Safari?** Skip to [section 1b](#1b-no-chrome-or-edge-set-up-the-wi-fi-from-your-phone-or-safari): the board can set up its own Wi-Fi.

## 1. Put the board on your Wi-Fi

1. Plug the board into the computer with the USB cable. The panel may light up.
2. In Chrome or Edge, open **https://dwooods.github.io/glow-grid/**.
3. In the **Board** card, press **Connect over USB**. Pick the board in the list the browser shows and press Connect. The card should say "Connected. Firmware 10." (If it says a lower number, the board needs a newer program: ask whoever sent it.)
4. Press **Network** at the top. Under "Set up the board's Wi-Fi", press **Scan for networks**. The panel freezes for a few seconds while the board listens; that is normal.
5. Pick your Wi-Fi from **Networks found**, type its password, and press **Save to board**.
6. Wait a few seconds. The dialog says "Joined ..." and shows the board's **address**, for example `192.168.1.50 (glowgrid-a1b2.local)`. The same address now shows at the top of the Board card, and the Network box is filled with the name. **Write both down.**

**Your network is not in the list?** The board only hears **2.4 GHz** Wi-Fi. A 5 GHz-only network never shows up. Many routers offer both; if yours has separate names, pick the one without "5G" in it. A hidden network is not listed: type its name in the box under the list. If it still does not show, move the board closer to the router and scan again.

**The board did not join?** Check the password and that the network is 2.4 GHz. Fix what is wrong and press Save to board again.

## 1b. No Chrome or Edge? Set up the Wi-Fi from your phone or Safari

The board makes its own setup network when it has no Wi-Fi saved, so you need no USB and no computer. It works from an iPhone, an Android phone, or a Mac or PC in any browser, Safari included.

1. Power the board from a USB charger. With no Wi-Fi saved, it opens a network called **GlowGrid-Setup-** and four digits, and keeps it open for 5 minutes.
2. **Look at the panel.** It shows 8 digits in two rows of four, and a blue bar along the bottom that shrinks as the 5 minutes run out. Those digits are the password. The board makes up a new name and a new password every time, so you have to be at the board to join.
3. On your phone or computer, join the **GlowGrid-Setup-…** Wi-Fi network and type the 8 digits as the password. The setup page opens by itself. If it does not, go to `http://192.168.4.1/`.
4. Pick your Wi-Fi from the list (or type its name), type its password, and press **Save**. The page counts down a few seconds while the board joins. The page shows the board's address, `glowgrid-` and four characters, then `.local`. **Write it down.**
5. **Forget the setup network** on your phone or computer (Wi-Fi settings, the `GlowGrid-Setup-…` entry, *Forget This Network*). Its name and password change every time, so a saved one can never rejoin.
6. Back on your home Wi-Fi, open the board's address in your browser, for example `http://glowgrid-1a2b.local/`. See section 2.

**Did not work?**
- The setup network closes after 5 minutes. A wrong Wi-Fi name or password brings it back, with new digits. If it is gone, unplug the board and power it again.
- If joining says "incorrect password", forget every old `GlowGrid-Setup-…` entry and join the one with the digits showing on the panel now.
- The setup network uses WPA3. Phones from before about 2018 cannot join it. Use a computer with Chrome or Edge and the USB steps in section 1 instead.
- The panel has to be connected and lit, because the password is drawn on it.

## 2. Use it from any device on your Wi-Fi

You can now unplug the computer and power the board from any USB charger. From a computer on the **same Wi-Fi**, open the same page, press **Network**, and press **Connect over Wi-Fi**. The address is the board's name: `glowgrid-` and four letters or digits, then `.local`. You wrote it down in step 6, and the Network box already holds it. If the name does not work, use the numbers instead.

- Chrome asks **once** whether the page may reach devices on your network. Choose **Allow**.
- The page says "Not secure" in the address bar. That is expected: the board speaks plain http inside your house.
- It works only on the same Wi-Fi as the board. A guest network, or a router with "client isolation" turned on, hides devices from each other.
- If the first try says "cannot reach the board", press **Connect over Wi-Fi** once more after you have chosen Allow.
- **Safari and iPhone:** the page at github.io cannot reach the board, because Safari does not let a secure (https) page talk to a plain-http device. Open the board's own address instead, `http://glowgrid-1a2b.local/` with your board's four characters, or `http://` and its numbers. The board serves the same editor itself, and it connects to the board without any button. Chrome and Edge can use either page.

## 3. Add sprites

Draw in the editor and press **Send to board**, or open the Board card and press **Add examples** to load the built-in ones. The board keeps them when it loses power and keeps playing without any computer.

## Putting it back to factory

In **Network**, with the board on USB, press **Forget network**. The board stops trying to join your Wi-Fi.

To move it to a different Wi-Fi without USB, open **Network** while connected over Wi-Fi and press **Change the board's Wi-Fi…**. The board opens its setup network, and you follow section 1b from step 2.
