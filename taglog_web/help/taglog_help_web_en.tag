Tag-help-version: 1.0
Description: Help topics rewritten for the web edition of taglog. Topics with the same Id as in taglog_help_en.tag replace the original text, which describes the Tcl/Tk windows.
End:
Id: About
Title: About Taglog
Description:: END_D
This is Taglog web edition, version $1.

It is a browser-based port of taglog, Copyright John Lines
<john+taglog@paladyn.org>. Taglog is Free Software, released under the terms
of the GNU General Public License, version 3. This port is a derivative work
under the same licence.

See https://github.com/JohnLines/taglog/wiki for the original taglog home page.

Most of these help pages are John Lines' original text. Pages that described
the windows of the original Tcl/Tk program have been rewritten to match this
version.
END_D
End:
Id: introduction
Title: Introduction
Description:: END_D
Taglog provides a way to measure how you spend your time, and to assist
with planning actions (tasks). You can book time to projects, which is the
term taglog uses for the way you divide your time for booking purposes.

If you want to book time to projects then you should create some projects
as your next step (Projects, then Add project...).

The main function of taglog is to make notes about how you spend your time.
On the Today page, choose a Project (and optionally an Activity) and type
notes about what you are doing into the Description box. Your notes are saved
automatically as you type.

When you switch to a different piece of work, press Next (or Ctrl/Cmd+Enter).
The entry is written to today's log with its start and end times, and a new
entry starts. Use the small arrow next to Next to start the new entry with a
particular activity.

Most cards and form fields have a small ? button which shows the help for
that item. You can also press the ? key (when you are not typing in a field)
to get help on the page you are looking at.

There is no need to "exit" at the end of the day. The entry you are working
on is saved continuously, and at midnight it is split between the two days.
END_D
End:
Id: file
Title: Days, logs and pausing
Description:: END_D
Log & search lets you look at the entries for any previous day, edit them,
and search for entries which match particular criteria, such as project,
activity, contact or words in the description.

You can edit an entry in today's log by clicking it in the Today's log list
on the Today page.

Pause and Resume allow the bookings clock to be stopped and started. Pause
writes the current entry to the log. You may wish to create a Breaks project
and switch to that instead (see Projects).

Settings allows you to customise several features of the program.

You can close the browser window at any time; the server keeps timing.
If you stop the server (close its Terminal window), the unfinished entry is
kept and continues when you start Taglog again.
END_D
End:
Id: actions
Title: Actions
Description:: END_D
The actions facility helps you to organise your 'todo' list.

New action... creates a new action.
Click an action in the list to see all its details, change them, change its
state (Activate, Complete, Abort, ...) with an optional note, add a subtask,
or see all the time that has been logged against it.

Use the checkboxes and filters at the top to choose which actions are shown,
for example only Active and Pending actions, or only those for one project,
up to a certain priority.

To record that you are working on an action, choose it in the Action field on
the Today page (only Active actions are offered there), or press
"Work on this now" in the action's window. The Complete action and Abort
action buttons on the Today page finish the current entry and change the
state of the current action in one step.

Reports, Active actions review shows how the time spent on your active
actions compares with what you expected.
END_D
End:
Id: projects
Title: Projects
Description:: END_D
Within taglog a project is a way you divide your time for booking purposes.
For the ability to schedule and control activities you should look at Actions.

Add project... creates a new project.
Click a project in the list to edit or delete it.
Tick "Show closed" to also list projects whose end date has passed.

The Project times today card on the Today page shows how today's time is
spread across projects, and lets you switch project with one click.
END_D
End:
Id: reports
Title: Reports
Description:: END_D
Taglog can produce a number of reports on the information it has collected.

'Weekly bookings' provides the information you need to feed into your
company time booking system, with the time spent on each project, per day,
and totaled for the week. It can be downloaded as a CSV file for a
spreadsheet.

'Time by activity' tells you where your time has been going in terms of
meetings, phone calls etc.

'Project total' goes through all the log entries for a project and adds up
the total time spent, with a breakdown by activity.

'Project progress' shows which actions for a project have been completed or
started in some time frame, which ones have slipped past their expected
completion date, and which are active.

'Active actions review' compares the time logged on each active action with
its expected time and date, and lets you revise those estimates.

'Interruptions' summarizes the information gathered from using the
Interrupt button, by telling you how often this happens over some period.
END_D
End:
Id: endbutton
Title: Current action buttons
Description:: END_D
These buttons work on the action you have chosen in the Action field.

Complete action writes the current entry to the log and marks the action as
Completed. If the action has a Next action, that action is made Active and
becomes the current action.

Abort action writes the current entry to the log and marks the action as
Aborted.

The Contact field associates a contact with the current entry. It is cleared
when you move to the next entry.

The Rate field associates a rate with the current entry. It is 'sticky': if
you indicate that you are now on Overtime rate you will stay on it until you
clear the rate. If an hourly rate is set in Settings, Overtime entries are
charged at the hourly rate multiplied by the overtime multiplier.
END_D
End:
Id: stack
Title: Interrupt, Push and Pop
Description:: END_D
The stack lets you record that you were interrupted, or that you put one
task aside to do another, and then go back to what you were doing.

Interrupt ! writes the current entry to the log, remembers its project and
action, and starts a new entry for the interruption. The new entry is marked
as an interruption (its Stack-info starts with !), which is what the
Interruptions report counts.

Push + does the same, but marks the new entry as a planned switch (+) rather
than an interruption.

Pop - writes the current entry to the log and starts a new entry with the
project and action that were in use before the matching Interrupt or Push.

You can interrupt an interruption: the stack can be several levels deep, and
the Today page shows the current depth.
END_D
End:
Id: adjstart
Title: Adjusting the start time
Description:: END_D
The ability to adjust the start time of an entry may be useful if, for
example, you were away from your desk, logging time to one project, and
someone diverts you to have a brief word, which turns into an extended
discussion, about some other project.

You can adjust the start time of the current entry with the Adjust... button
next to the Start time. You can either type the revised start time, or use
the slider to subtract some number of minutes.

If this is not the first entry of the day then you are offered the chance to
change the end time of the previous entry to match the new start time. This
is the default. If you do not adjust the end time of the previous entry then
you will double account for the time by which you adjusted the start.

The start cannot be moved back past the start of the previous entry (that
would make the two entries overlap). If the previous entry is very short -
for example because you pressed Next twice - the dialog tells you so and
offers to edit that entry; delete or shorten it, then adjust again.
A start time in the future is not accepted.

You can also type a new time directly into the Start field.
END_D
End:
Id: logedit
Title: Editing log entries
Description:: END_D
According to The Rubaiyat of Omar Khayyam (translated by Edward Fitzgerald)

 The Moving Finger writes; and, having writ,
 Moves on; nor all thy Piety nor Wit
 Shall lure it back to cancel half a Line,
 Nor all thy Tears wash out a Word of it.

Taglog, however, gives you the chance to click on any entry, in Today's log
or in Log & search, and edit or delete it.
END_D
End:
Id: logedit_start
Title: Log entry field: start
Description:: END_D
You can change the start time of this entry - though note that the end time
of the preceding entry is not adjusted automatically.

You will have to do this yourself if you want to keep your logs consistent.
For the entry you are working on now, use the Adjust... button on the Today
page, which can move the previous entry's end time as well.
END_D
End:
Id: logsel
Title: Searching the log
Description:: END_D
Use the From and To dates to choose which days are searched. You can use the
other fields to restrict which entries are shown: all the conditions you fill
in must match.

Tick "Show day summaries only" to see just the summaries you wrote for each
day.

Click a day's heading to open that day, or click an entry to edit it.
Copy as text copies the results so you can paste them elsewhere.
END_D
End:
Id: actsel
Title: Choosing which actions to show
Description:: END_D
There are several ways to select a set of actions. The controls at the top of
the Actions page set the attributes of the actions you wish to see.

The attributes are cumulative, so actions must match all the criteria to be
shown. The Text field matches words in the title, Id or description.
END_D
End:
Id: actsel_st
Title: Selecting actions: status
Description:: END_D
Only actions with a status which matches one of the ticked checkboxes are
shown. Tick all of them to see every action.
END_D
End:
Id: actreminder
Title: Today's actions
Description:: END_D
Use these fields to give you a reminder of the actions you plan to do today.
They are just ordinary text fields and are not tied in to the main actions
data, although titles of active actions are offered as suggestions.

They are saved in today's log file, so you can look back and remind yourself
what you were planning to work on.
END_D
End:
Id: viewproject
Title: Project times today
Description:: END_D
This card lists the projects marked as Active, and any project you have
booked time to today. For each project it shows:

Total booked - all the time logged on the project since its start date,
including the entry you are working on now.
Today - the time booked to the project today.
Expected - the project's Expected time (set on the Projects page).
Remaining - the expected time minus the total booked. When the total booked
is more than the expected time it is shown in red as a negative value, and
the project is marked "over budget".

At the bottom, Booked today is the total of all the time booked today, and
Booked today (non breaks) leaves out projects labelled as breaks.

You can switch to a different project by clicking it: the current entry is
written to the log and a new one starts on that project.
END_D
End: 
Id: summarybox
Title: Day summary
Description:: END_D
Enter a summary of the day's events here. It is stored in the day's log file
and can be shown on its own with "Show day summaries only" in Log & search.

You can write or change the summary for any day, from the Today page or from
Log & search.
END_D
End:
Id: timebooksel
Title: Weekly bookings report
Description:: END_D
Here you can control the generation of the time bookings report.
You can display the times in the report as hours and minutes, or as
decimal fractions of hours, or as decimal fractions of days.

The Hours worked per day setting controls the conversion for decimal
fractions of days.

If you choose to spread overheads then the time booked to projects which
are flagged as Overheads is distributed across all the other projects
(apart from those flagged as Breaks or Immutable).

You can choose how the projects are labelled: by booking code, by name or
both together. If you have more than one project with the same booking code
and you label by code then the totals for those projects are amalgamated.
Projects without a booking code are shown by name.

Choose the Monday the report starts on, and how many weeks to show. Use
Previous week and Next week to move through the weeks. Download CSV saves
the report for a spreadsheet.

If an hourly rate is set in Settings, the report also shows, for each
project and for the week, the overtime and the amount. Spread overheads
carry their amount with them in the same proportion as their time.
END_D
End:
Id: timebooksel_spreadoverheads
Title: Spreading overheads
Description:: END_D
The time booked to projects which are flagged as Overheads can be
redistributed across other projects.

If this is set to Off then no redistribution occurs and Overheads projects
are shown in the report.

If this is set to By week then each day's overheads time is shared amongst
the other projects in proportion to the time booked to them over the whole
week.

If this is set to By day then each day's overheads time is shared amongst
only the projects booked on that same day, in proportion to their time that
day.

Projects which are labelled as Immutable or Breaks do not take part in the
redistribution.
END_D
End:
Id: editprefs
Title: Settings
Description:: END_D
Taglog stores your settings in the preferences file shown at the top of the
Settings page (normally ~/.taglog). It is the same file the original
Tcl/Tk taglog uses, and both programs can share it.

Only the lines for settings you change are rewritten. Anything you have added
yourself below the line "# above this line is automatically saved" is kept.
END_D
End:
Id: prefs_activitiesfile
Title: Setting: activities file
Description:: END_D
The activities file holds the names of the types of activity which you wish
to record, one activity type per line.

If you leave this setting blank the file "activities" in your data directory
is used. You can edit the list directly in the Activities box on the Settings
page; the change takes effect as soon as you save.
END_D
End:
Id: prefs_language
Title: Setting: language
Description:: END_D
This field indicates your preferred language, as an ISO 639 language code.
At present only the help information is available in more than one language,
and only English and German are complete; for topics that have not been
translated the English text is shown.

You can also switch language for a moment from the Help page.
END_D
End:
Id: editprefs_num_today_actions
Title: Setting: number of today's actions
Description:: END_D
You can keep a reminder of your top 'n' actions for the day on the Today page.
Setting this to 0 removes the Today's actions card completely.
END_D
End:
Id: actinput_id
Title: Action field: Id
Description:: END_D
Every action is given a unique identifier. If you leave the Id field empty
then an Id will be generated automatically.

If the action is associated with a project then the Id is generated from the
name of the project (with spaces changed to underscores), followed by a serial
number which increments with each action for that project - for example
test_project.57

If the action is not associated with a project then the identifier is of the
form taglog.yyyymmddhhmmss - taken from the current date and time - for
example taglog.20001119094500

The Id cannot be changed once the action has been created.
END_D
End:
Id: actinput_active_after
Title: Action field: Active after
Description:: END_D
If you set a date, and optionally a time (YYYY-MM-DD HH:MM), when you create
an action, then the action is entered as being Blocked (unless it is
Delegated).

Once that time has passed, a notice appears at the top of the Today page with
the action's title and an Activate button. This allows you to use the system
for timed reminders.
END_D
End:
Id: actinput_period
Title: Action field: Period
Description:: END_D
For an action with a status of Periodic, the frequency or Period with which
this action becomes active again. It is in the format

Period: Daily|Weekly|Monthly|Yearly [when]

where when is an optional number for the hour of day, or day of week or month
when the action becomes due again.

This version stores the Period, so it is kept for the original taglog, but it
does not yet remind you about periodic actions.
END_D
End:
Id: actinput_email_status_to
Title: Action field: Email status to
Description:: END_D
In the original taglog, if you set this field, and your email preferences
have been set up, a mail message is sent to the given address every time the
status of the action changes.

This version stores the address but does not send any mail yet.
END_D
End:
Id: hint_problem_actions_overrun
Title: Hint: actions overrun
Description:: END_D
If you find that actions are taking longer than you originally expected then
you are probably being too optimistic at the outset. If you are not already
doing so, try to start entering initial estimates of expected elapsed time
when you enter actions. Review your active actions regularly, using
Reports, Active actions review, and update the Expected time and Expected
completion entries.

When you revise an estimate the original estimate is kept on the action
(Original-expected-time and Original-expected-completed-date), so you can
compare your latest estimates with the original ones. Use this information to
help you give better original estimates in future.
END_D
End:
Id: prefs_rates
Title: Setting: rates
Description:: END_D
If you set an hourly rate, the Weekly bookings report and the Project total
report also show amounts (and the CSV download includes them).

Hourly rate: the amount charged per hour of normal time.

Overtime multiplier: entries whose Rate is Overtime are charged at the hourly
rate multiplied by this number. For example, with an hourly rate of 40 and a
multiplier of 1.5, an hour of overtime is charged 60. You mark entries as
Overtime with the Rate field on the Today page.

Currency: shown in front of amounts, for example € or CHF. It is only a label;
no conversion is done.

Time on projects marked as Breaks is not charged. Leave the hourly rate empty
to hide amounts.

These settings are only used by this version of taglog. They are saved below
the "automatically saved" line in your preferences file, where the original
taglog leaves them alone.
END_D
End: 
Id: project_expectedtime
Title: Project expected time
Description:: END_D
Enter the total time you expect to spend on this project over its lifetime,
in hours (for example 40, or 40.5) or in hours and minutes (for example 40:30).

Reports, Project total compares the time actually logged on the project with
this expected time and shows the time remaining. When the actual time is more
than the expected time it is shown in red and marked "over budget".
END_D
End: 
