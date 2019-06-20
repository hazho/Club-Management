import telegram
from django.core.management.base import BaseCommand
from status.management.fetch_status_updates import DailyStatus
from datetime import date, datetime, timedelta
from members.models import Profile
from status.models import StatusRegister
from framework import settings
from pytz import timezone


class Command(BaseCommand):
    help = 'Logs Daily Status Updates'

    def add_arguments(self, parser):
        parser.add_argument('day', nargs='?', type=int)
        parser.add_argument('month', nargs='?', type=int)
        parser.add_argument('year', nargs='?', type=int)

        parser.add_argument(
            '--send-telegram-report',
            action='store_true',
            dest='send_telegram_report',
            help='Whether to send report on telegram group',
        )

    def handle(self, *args, **options):
        d = date.today()

        # Checks if specific date to fetch status update is provided
        if options['day'] and options['month'] and options['year']:
            d = date(options['year'], options['month'], options['day'])

        log = DailyStatus(d)
        profiles = Profile.objects.filter(email__in=log.emails)

        # Logs Status Updates into CMS Database
        i = 0
        for profile in profiles:
            if profile.user.is_active:
                StatusRegister.objects.create(member=profile.user, timestamp=log.members[profile.email])
                i += 1

        if options['send_telegram_report']:
            today = datetime.combine(d, datetime.min.time())
            maxt = today.replace(hour=23, minute=00)
            mint = today.replace(hour=18, minute=00)
            members_list = Profile.objects.values('user', 'first_name', 'last_name', 'email', 'batch').order_by('batch')
            members_count = Profile.objects.filter(batch__gt=d.year-4).count()

            updates = StatusRegister.objects.filter(timestamp__gt=mint,timestamp__lt=maxt).order_by('timestamp')
            if i > 0:
                first = Profile.objects.get(user=updates[0].member)
                fn = first.first_name
                ft = updates[0].timestamp

                u = list(reversed(updates))
                last = Profile.objects.get(user=u[0].member)
                ln = last.first_name
                lt = u[0].timestamp

            # Composing Status Update Report Message for Telegram
            message = '<b>Daily Status Update Report</b> \n\n &#128197; ' + d.strftime('%d %B %Y') + ' | &#128228; ' +str(i) + '/' + str(members_count) + ' Members'
            if i/members_list.count() > 0.90:
                message += '''\n\n<b>More than 90% of members sent their status update today.</b>'''
            elif i/members_list.count() > 0.75:
                message += '''\n\n<b>More than 75% of members sent their status update today.</b>'''
            elif i/members_list.count() < 0.25:
                message += '''\n\n<b>Less than 25% of members sent their status update today.</b>'''
            elif i/members_list.count() < 0.10:
                message += '''\n\n<b>Less than 10% of members sent their status update today.</b>'''
            if i > 0:
                message += '''\n\n<b>&#11088; First to Send: </b>'''
                message += fn + ' (' + ft.astimezone(timezone('Asia/Kolkata')).strftime('%I:%M %p') + ')\n'
                message += '''<b>&#128012; Last to Send: </b>'''
                message += ln + ' (' + lt.astimezone(timezone('Asia/Kolkata')).strftime('%I:%M %p') + ')\n'
            mf = 0

            #Reports of people who send report lately
            lateLogs = StatusRegister.objects.filter(timestamp__gt=maxt).order_by('timestamp')
            if lateLogs.count() > 0:
                message += '''\n\n<b>Members who were late to sent their status update: </b> \n'''
            for m in members_list:
                obj = lateLogs.filter(member=m['user'])
                if obj:
                    message += m['first_name'] + ' [' + str(obj[0].timestamp.astimezone(timezone('Asia/Kolkata')).strftime('%I:%M %p')) + '] \n'

            # Reports are generated only for the last 4 batches from current year
            for y in range(d.year, d.year-4, -1):
                yf = 0
                for m in members_list:
                    if m['email'] not in log.emails and y == m['batch']:
                        if not mf:
                            message += '''\n\n<b>Members who didnt send status updates:</b> \n'''
                            mf = 1
                        if not yf:
                            message += '\n<b>' + str(y) + '</b>\n'
                            yf = 1


                        message += m['first_name'] + ' '
                        if type(m['last_name']) is str:
                            message += m['last_name']
                        obj = StatusRegister.objects.filter(member=m['user']).order_by('-timestamp')
                        if obj:
                            last = obj[0]
                            diff = d-last.timestamp.date()
                            if diff.days > 28:
                                message += ' [1M+, '
                            elif diff.days > 21:
                                message += ' [3W+, '
                            elif diff.days > 14:
                                message += ' [2W+, '
                            elif diff.days > 7:
                                message += ' [1W+, '
                            else:
                                message += ' [ ' + str(diff.days) + 'D, '
                            month_ago = d - timedelta(days=31)
                            count = obj.filter(timestamp__gt=month_ago).count()
                            message += str(count) + '/31 ]'
                        else:
                            message += '[ NSB ]'
                        message += '\n'
            if not mf:
                message += '\n\n<b>Everyone has send their Status Updates today! &#128079;</b>\n'

            message += '\n<i>This is an automatically generated message. Please send your status updates daily.</i>'
            print(message)
            bot = telegram.Bot(
                token=settings.TELEGRAM_BOT_TOKEN)
            bot.send_message(
                chat_id=settings.TELEGRAM_GROUP_ID,
                text=message,
                parse_mode=telegram.ParseMode.HTML
            )

