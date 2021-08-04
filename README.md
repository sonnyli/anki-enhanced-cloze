# Enhanced cloze 2.1
This add-on allows to improve clozes usage. See the [AnkiWeb page](https://ankiweb.net/shared/info/1990296174) for more details. 

## Known Limitations, Bugs, Todo
- On Ankidroid 2.9 with Android 10 in 2019-11-27 it doesn't work properly: When you have multiple
  c1s and on Ankidroid you touch the first one to unveil it it immediatly jumps to the answer and
  unveils all. I'm not sure that this is expected/desired behavior. On the other hand "Cloze Hide
  All" from 2019-11-27 also behaves like this: when you unveil one cloze of multiple the answer is
  revealed (and Cloze Hide All doesn't highlight the cloze as nicely and doesn't scroll to the
  first).
- might not work on ios, see negative review from 11/24/2019. I don't have an ipad or iphone
- for Anki 2.1.20 or lower: arrow keys don't work in the browser table: second arrow press is redirected 
  to scroll in editor instead of going to the next note. Not very relevant since I can use Ctrl+n/p to go 
  through the list, for details see https://github.com/Arthur-Milchior/anki-enhanced-cloze/issues/11
- the version for 2.0 allows "to go without clozes using this cloze-type templates. Just type
  question in Content field and answer in Note field.". I removed this in 2019-11 because a side
  effect was that when using the ctrl+shift+c shortcut clozes always started with c2 ...

## Warning
Make a backup before updating from 2.0 note type to 2.1 note type.

If you used those cards with anki 2.0, you need:
* either to change the note type to "Enhanced cloze 2.1" [Improving «change note
  type»](https://ankiweb.net/shared/info/513858554) may help you to do the change more safely, since
  those are clozed note.
* or to copy the front of the note type "Enhanced cloze 2.1" to "Enhanced cloze", remove "Enhanced
  cloze 2.1" and rename "Enhanced cloze" to "Enhanced cloze 2.1" (this one is more technical, but
  also safer)


## Links, licence and credits

Key              |Value
-----------------|-------------------------------------------------------------------
Version 2.0 by   | [https://github.com/luzhe610/anki-enhanced-cloze](luzhe610)
Ported to 2.1 by | Arthur Milchior <arthur@milchior.fr>
Based on         | Anki code by Damien Elmes <anki@ichi2.net>
License          | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
Source in        | https://github.com/Arthur-Milchior/anki-enhanced-cloze
Addon number     | [2062736101](https://ankiweb.net/shared/info/2062736101)
Support luzhe610 | https://www.paypal.me/LuZhe610
Support Arthur   | [![Ko-fi](https://ko-fi.com/img/Kofi_Logo_Blue.svg)](Ko-fi.com/arthurmilchior) or [![Patreon](http://www.milchior.fr/patreon.png)](https://www.patreon.com/bePatron?u=146206)
