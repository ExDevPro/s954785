The Dashboard: Your Mission Control
When you first open the software, you'll see the Dashboard. This is your at-a-glance view of everything you have set up.

Stat Cards: You'll see several cards for Leads, SMTPs, Subjects, Messages, Attachments, and Proxies. Each card shows you two numbers: the number of lists you have and the total number of items within those lists. For example, the "Leads" card might show "2 (1500)," which means you have two lead lists with a total of 1,500 email addresses. You can click on any of these cards to go directly to that section.

Chart: There's also a chart that gives you a visual breakdown of your assets and campaign statuses.

At the top left, you'll find the main navigation menu to access each feature.

=================================

Core Components: The Building Blocks of Your Campaigns
Before you can send emails, you need to set up the different parts of your campaign. Each has its own manager.

Leads Manager: Your Audience
This is where you manage your email lists.

How to Use:
Click "New List" to create a new, empty list.
Select a list and click "Import" to add leads from an Excel file (.xlsx/.csv). You can merge new leads into an existing list.

Once loaded, you'll see your leads in a table. You can edit any information directly in the table.

Use the "Filter leads..." box to quickly find specific emails.

The "Remove duplicate rows" button will clean up your list by removing any identical entries.

When you're done, click "Save".

you can use/resuse same list with multiple campaigns at a same time if needed.


=================================
SMTP Manager: Your Sending Engine
This is where you'll add and manage your SMTP server details, which are used to send the emails.

How to Use:

Create a "New List" to organize your SMTP servers.

Click "Import SMTP File" to load a list of SMTPs from an Excel /csv file.

To add a single SMTP server, click "Add New SMTP" and fill in the details (Host, Port, User, Password, etc.).

The most important feature here is testing. You can "Test All SMTPs" at once or test a single one. This will tell you if the server is working correctly. The status will show as "Success" or "Fail".

Always "Save" your changes.

=============================

Subject Manager: Your Opening Line
Here, you can create and manage lists of different email subjects. The software will rotate through them during a campaign.

How to Use:

Create a "New" list.

You can "Import" subjects from a text, CSV, or Excel file.

You can also add subjects by typing them directly into the table.

Use the "De-dupe" button to remove any duplicate subjects.

Click "Save" to keep your changes.


==========================

Message Manager: Your Email Content
This is where you manage your email templates (the body of the email).

How to Use:

First, create a "New List" to organize your message templates.

Then, click "Import Message(s)" to import your email files (.html or .txt). If your HTML file uses images that are in the same folder, the software will automatically import them too.

You can "Preview/Edit" any message. The editor lets you make changes, format text (bold, italic, etc.), and switch between a desktop and mobile view to see how your email will look on different devices.

=============================

Attachment Manager: Your Files
If you need to send files with your emails, you'll manage them here.

How to Use:

Create a "New List" for your attachments.

Click "Import Files/Folder" to add files to the list. The software automatically prevents you from adding files with the same name to the same list.

You can see the filename, size, and date modified in the table.

==========================

Proxy Manager: For Advanced Sending
If you use proxies for sending, this is where you'll manage them.

How to Use:

Create a "New List".

"Import" your proxies from a text file.

You can "Test All" your proxies to see which ones are live and which are dead.

The "Remove Dead" button will clean up your list by removing any proxies that failed the test.

"Save" your changes.

==========================

Campaign Builder: Putting It All Together
This is where the magic happens! The Campaign Builder lets you combine all the elements you've set up into a sending campaign.

How to Use:

Start by creating a "New" campaign and giving it a name.

In the "Data Lists" section, you'll see dropdown menus for each component. Select the Lead List, SMTP List, Subject List, and Message List you want to use. You can also optionally select an Attachment List and a Proxy List.

Next, choose your "Sending Mode":

No Delay: Sends emails as fast as possible.

Custom Delay: Lets you set a random delay (in seconds) between each email.

Batch Mode: Sends emails in batches, with a delay between each batch.

Spike Mode: Allows you to schedule sending over several days with a specific number of emails per day.

Once you have everything configured, click "Save Config".

When you're ready to start, click the "Launch Campaign" button!

You'll see a progress bar and a log that shows the status of each email being sent.

can start/run/manage multiple campaigns at a same time each campaign will use their own thread/data.
==========================

Settings: Customize Your Experience
Finally, the Settings section lets you personalize the software. Right now, this is where you can change the Application Theme to a look and feel that you prefer.

I hope this gives you a great starting point! The best way to learn is to jump in and start playing around with each feature. If you have any more questions, just ask!
