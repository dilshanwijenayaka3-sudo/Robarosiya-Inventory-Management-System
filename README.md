# ROBAROSIYA HOTEL INVENTORY SYSTEM

A simple, offline-first Windows inventory application for one computer. Interface in English. Uses Flask and SQLite, with the hotel logo included.

## Setup on Windows

1. Extract the ZIP completely (do not run from inside the ZIP).
2. Install Python 3.10+ from python.org, enabling **Add python.exe to PATH**.
3. Double-click `start.bat`. Internet is required once to install Flask if it isn't already installed.
4. Wait until it says `Robarosiya Inventory running at http://127.0.0.1:5000`. Your browser should open automatically, or visit that address manually.
5. On first launch, create an Admin username/password (8+ characters). Log in.
6. The Admin adds Items and Staff accounts. Both Admin and Staff can perform Stock In and Stock Out.
7. **Keep the command window open while using the app.** Close the window to stop the app.

If `start.bat` flashes and closes: open the extracted folder in File Explorer, click the folder address bar, type `cmd`, press Enter, type `start.bat`, and share any error shown.

## Pages
- Dashboard: item counts, stock value, low stock alerts, expiry alerts, recent activity, **fixed asset counts** (chairs, plates, etc.)
- Items: Admin adds/edits/archives; Staff can view
- Stock In: quantities, optional expiry date, purchase cost
- Stock Out: issue to Kitchen, Bar, Housekeeping, Maintenance, Other, Restaurant; unexpired batches consumed by earliest expiry first
- Reports: daily, monthly and all-time transactions; department usage; CSV export; printing
- Staff Accounts: Admin creates/disables staff and downloads SQLite backups

## Data and backups
- Your database is stored locally in `data/inventory.db`. It is NOT uploaded to the Internet.
- The Admin can download a database backup on the Staff Accounts page. Copies are also saved to `backups/`.
- Do not delete the `data` folder. Back it up regularly to external storage. To restore, close the app, make a safety copy of the current database, and replace `data/inventory.db` with the desired backup.
- Users' passwords are stored as password hashes. The first administrator is created on initial launch; there are no default credentials.

## Important limitations
- This version is designed for a single PC, not simultaneous multi-user network use.
- The stock valuation on the dashboard is based on each item's latest unit price, not a full financial costing method.
- Stock Out cannot use expired batches, but expired stock remains counted until separately handled. Do not treat expiry alerts as automatic stock disposal.
- It doesn't include returns, corrections, transfers, detailed purchase orders, or accounting integrations.
- Test with sample stock before using for real hotel operations.

## Fixed Assets / Furniture Counts
- New **Fixed Assets** page: admin can add, change quantity/name/location, or delete chair/plate/furniture/equipment counts. Staff may view counts.
- The Dashboard displays all fixed asset counts in cards. Initial examples are **Chairs** and **Plates**, both with quantity **0** until you enter actual hotel counts.
- These are separate from consumable inventory and are not automatically changed by Stock In/Out.
- Existing user accounts and inventory data are preserved when replacing app files, **as long as you preserve the existing `data` folder**. Make a backup before upgrading.
