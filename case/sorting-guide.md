# Sorting guide for intercepted messages

Prepared by D. Okafor, Economic Offences Wing, for LANTERN's message classifier. Version 3.
Every example below is invented for training. None is taken from an exhibit.

## The three labels

Every message gets exactly one label.

**threat**: the message tries to frighten, pressure or silence the person who receives it. It
does not need to contain a threat of violence. Warnings about what will happen "if" the reader
keeps asking, talks to someone, or goes somewhere are threats. So are messages that show the
sender knows where the reader is, who their family are, or what they have been doing, when there
is no ordinary reason for the sender to say so.

**logistics**: the message is about work. Ships, berths, tugs, cargo, schedules, crews, invoices,
payments, audits, meetings, reports, access badges, rotas and suppliers are all logistics. A
message from a colleague about a deadline is logistics even if the tone is sharp.

**personal**: the message is about the reader's private life. Family, friends, health, children,
school, meals, holidays, sport, birthdays and anything domestic.

## Rules for the hard cases

1. Judge the message, not the sender. A message from a colleague can be personal ("Happy
   birthday, see you Friday") and a message from a relative can be logistics ("Your car is ready
   at the garage, the invoice is on the table" is personal, because the car is private; "The
   auditors moved the meeting to Tuesday" from a spouse who works at the same firm is logistics).
2. Pressure about work is still a threat when it is aimed at the person and not the task. "The
   report is late" is logistics. "Think carefully about what goes in that report" is a threat.
3. A question can be a threat. "Are you still at the office?" from someone with no reason to ask,
   at night, is a threat if the context makes it one. On its own, with no context, file it as
   logistics and flag it for a person.
4. Money does not decide the label. An invoice reminder is logistics. "Your family's expenses
   must be hard to meet" is a threat.
5. Unknown numbers are not threats by default. "Your parcel is held at the depot" from an unknown
   number is logistics.
6. Sarcasm and jokes between friends are personal. Do not read menace into a friend's teasing
   unless the message also shows pressure or knowledge it should not have.
7. When a message mixes two labels, choose the one that matters more to an investigator: threat
   over logistics, logistics over personal.
8. Do not use the time of day alone. Night messages about tugs are logistics.

## Worked examples

Each example is a message and the label it gets, with the reason.

- "Berth 4 is free from 06:00, bring the Aster Line vessel in early." logistics: a berthing
  schedule.
- "Crew change for the Coral Bay postponed to Thursday, customs paperwork incomplete."
  logistics: crew and customs.
- "Invoice KT-2291 is thirty days overdue, please confirm payment date." logistics: an invoice.
- "The quarterly audit starts Monday, have the fuel receipts ready." logistics: an audit.
- "Pilot boat delayed by fog, expect forty minutes." logistics: an operational delay.
- "Your new badge is at reception, the old one stops working tonight." logistics: site access.
- "Meeting with the port authority moved to 15:30, room 2." logistics: a meeting.
- "Can you sign off the overtime sheet before payroll closes?" logistics: payroll.
- "Your parcel is held at the depot, bring ID." logistics: an ordinary delivery notice from an
  unknown number (rule 5).
- "Tugs confirmed for the late tide, 23:10, pier 6." logistics: night operations (rule 8).
- "Dinner at my sister's on Sunday, she asked if you still like lamb." personal: family.
- "Mia lost her first tooth, she wants you to see it before bed." personal: a child.
- "The dentist can see you Wednesday at 4." personal: health.
- "Happy birthday! Drinks on Friday, no excuses." personal: friends, even from a colleague
  (rule 1).
- "Your mother called, she is feeling better after the hospital visit." personal: family health.
- "Did you book the ferry for the summer? Prices go up next week." personal: a holiday.
- "Football at seven, bring the spare shin pads." personal: sport.
- "You call that a pass? My grandmother kicks harder." personal: teasing between friends
  (rule 6).
- "It would be a shame if your questions reached the wrong people." threat: a warning about
  asking questions.
- "We know which school your daughter goes to." threat: knowledge of family, with no reason.
- "Stop looking at the shipping accounts. This is the only time we will ask." threat: an
  instruction to stop, with pressure.
- "Think carefully about what goes in that report." threat: pressure aimed at the person
  (rule 2).
- "Nice car. Shame about the brakes on that road." threat: menace disguised as small talk.
- "Your family's expenses must be hard to meet on one salary." threat: money used as pressure
  (rule 4).
- "Someone saw you at the registry office on Tuesday. Why were you there?" threat: shows the
  sender has been watching.
- "The report is late again." logistics: about the task, not the person (rule 2).
- "Are you still at the office?" logistics, flag for a person: a question with no context
  (rule 3).
- "Stay away from the east gate tonight, they are resurfacing it." logistics: a site notice, not
  a warning about the reader.
- "Keep this between us, the auditors do not need to see the draft." threat: asks the reader to
  hide something from an audit, which is pressure to stay silent (rule 7 puts threat first).
- "Payment for the Lindqvist cargo is in, thanks for chasing." logistics: a payment.

## Output

Answer with exactly one word, in lower case: threat, logistics or personal. No punctuation, no
explanation. If a message is empty or unreadable, answer logistics and a person will check it.
