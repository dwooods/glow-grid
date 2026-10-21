# Setting up your Glow Grid board

One-time setup, about five minutes. You need a computer (Windows, Mac or Linux) with **Chrome or Edge**, the board, and a USB-C cable that carries data (some charging cables do not). Safari and Firefox cannot do this step. A phone cannot either, because it cannot open a USB port.

## 1. Put the board on your Wi-Fi

1. Plug the board into the computer with the USB cable. The panel may light up.
2. In Chrome or Edge, open **https://dwooods.github.io/glow-grid/**.
3. In the **Board** card, press **Connect over USB**. Pick the board in the list the browser shows and press Connect. The card should say "Connected. Firmware 10." (If it says a lower number, the board needs a newer program: ask whoever sent it.)
4. Press **Network** at the top. Under "Set up the board's Wi-Fi", press **Scan for networks**. The panel freezes for a few seconds while the board listens; that is normal.
5. Pick your Wi-Fi from **Networks found**, type its password, and press **Save to board**.
6. Wait a few seconds. The dialog says "Joined ..." and shows the board's **address**, for example `192.168.1.50 (glowgrid-a1b2.local)`. The same address now shows at the top of the Board card, and the Network box is filled with the name. **Write both down.**

**Your network is not in the list?** The board only hears **2.4 GHz** Wi-Fi. A 5 GHz-only network never shows up. Many routers offer both; if yours has separate names, pick the one without "5G" in it. A hidden network is not listed: type its name in the box under the list. If it still does not show, move the board closer to the router and scan again.

**The board did not join?** Check the password and that the network is 2.4 GHz. Fix what is wrong and press Save to board again.

## 2. Use it from any device on your Wi-Fi

You can now unplug the computer and power the board from any USB charger. From a computer on the **same Wi-Fi**, open the same page, press **Network**, and press **Connect over Wi-Fi**. The address is the board's name: `glowgrid-` and four letters or digits, then `.local`. You wrote it down in step 6, and the Network box already holds it. If the name does not work, use the numbers instead.

- Chrome asks **once** whether the page may reach devices on your network. Choose **Allow**.
- The page says "Not secure" in the address bar. That is expected: the board speaks plain http inside your house.
- It works only on the same Wi-Fi as the board. A guest network, or a router with "client isolation" turned on, hides devices from each other.
- Safari and iPhone are not supported yet.

## 3. Add sprites

Draw in the editor and press **Send to board**, or open the Board card and press **Add examples** to load the built-in ones. The board keeps them when it loses power and keeps playing without any computer.

## Putting it back to factory

In **Network**, with the board on USB, press **Forget network**. The board stops trying to join your Wi-Fi.
