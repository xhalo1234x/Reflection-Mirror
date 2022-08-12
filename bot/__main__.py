from datetime import datetime
from os import execl as osexecl
from os import path as ospath
from os import remove as osremove
from signal import SIGINT, signal
from subprocess import check_output
from subprocess import run as srun
from sys import executable
from time import time

import pytz
from psutil import (
    boot_time,
    cpu_count,
    cpu_percent,
    disk_usage,
    net_io_counters,
    swap_memory,
    virtual_memory,
)
from telegram import InlineKeyboardMarkup, ParseMode
from telegram.ext import CommandHandler

from bot import *

from .helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time
from .helper.ext_utils.db_handler import DbManger
from .helper.ext_utils.fs_utils import clean_all, exit_clean_up, start_cleanup
from .helper.ext_utils.telegraph_helper import telegraph
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.button_build import ButtonMaker
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.message_utils import (
    editMessage,
    sendLogFile,
    sendMarkup,
    sendMessage,
)
from .modules import (
    authorize,
    bt_select,
    cancel_mirror,
    clone,
    count,
    delete,
    eval,
    hash,
    leech_settings,
    list,
    mediainfo,
    mirror_leech,
    mirror_status,
    rss,
    search,
    shell,
    sleep,
    speedtest,
    usage,
    wayback,
    ytdlp,
)

try:
    import heroku3
except ModuleNotFoundError:
    srun("pip install heroku3", capture_output=False, shell=True)
try:
    import heroku3
except Exception as f:
    LOGGER.warning(
        "heroku3 cannot imported. add to your deployer requirements.txt file."
    )
    LOGGER.warning(f)
    HEROKU_APP_NAME = None
    HEROKU_API_KEY = None


def getHerokuDetails(h_api_key, h_app_name):
    try:
        import heroku3
    except ModuleNotFoundError:
        run("pip install heroku3", capture_output=False, shell=True)
    try:
        import heroku3
    except Exception as f:
        LOGGER.warning(
            "heroku3 cannot imported. add to your deployer requirements.txt file."
        )
        LOGGER.warning(f)
        return None
    if (not h_api_key) or (not h_app_name):
        return None
    try:
        heroku_api = "https://api.heroku.com"
        Heroku = heroku3.from_key(h_api_key)
        app = Heroku.app(h_app_name)
        useragent = getRandomUserAgent()
        user_id = Heroku.account().id
        headers = {
            "User-Agent": useragent,
            "Authorization": f"Bearer {h_api_key}",
            "Accept": "application/vnd.heroku+json; version=3.account-quotas",
        }
        path = "/accounts/" + user_id + "/actions/get-quota"
        session = requests.Session()
        result = (session.get(heroku_api + path, headers=headers)).json()
        abc = ""
        account_quota = result["account_quota"]
        quota_used = result["quota_used"]
        quota_remain = account_quota - quota_used
        abc += f"<b></b>\n"
        abc += f"<b>╭─《🌐 HEROKU STATS 🌐》</b>\n"
        abc += f"<b>│</b>\n"
        abc += f"<b>├ 💪🏻 FULL</b>: {get_readable_time(account_quota)}\n"
        abc += f"<b>├ 👎🏻 USED</b>: {get_readable_time(quota_used)}\n"
        abc += f"<b>├ 👍🏻 FREE</b>: {get_readable_time(quota_remain)}\n"
        # App Quota
        AppQuotaUsed = 0
        OtherAppsUsage = 0
        for apps in result["apps"]:
            if str(apps.get("app_uuid")) == str(app.id):
                try:
                    AppQuotaUsed = apps.get("quota_used")
                except Exception as t:
                    LOGGER.error("error when adding main dyno")
                    LOGGER.error(t)
            else:
                try:
                    OtherAppsUsage += int(apps.get("quota_used"))
                except Exception as t:
                    LOGGER.error("error when adding other dyno")
                    LOGGER.error(t)
        LOGGER.info(f"This App: {str(app.name)}")
        abc += f"<b>├ 🎃 APP USAGE:</b> {get_readable_time(AppQuotaUsed)}\n"
        abc += f"<b>├ 🗑️ OTHER APP:</b> {get_readable_time(OtherAppsUsage)}\n"
        abc += f"<b>│</b>\n"
        abc += f"<b>╰─《 ☣️ @dipeshmirror ☣️ 》</b>"
        return abc
    except Exception as g:
        LOGGER.error(g)
        return None


IMAGE_X = "http://telegra.ph/REFLECTION-07-18"

now = datetime.now(pytz.timezone(f"{TIMEZONE}"))


def progress_bar(percentage):
    p_used = "⬢"
    p_total = "⬡"
    if isinstance(percentage, str):
        return "NaN"
    try:
        percentage = int(percentage)
    except BaseException:
        percentage = 0
    return "".join(p_used if i <= percentage // 10 else p_total for i in range(1, 11))


def stats(update, context):
    if ospath.exists(".git"):
        last_commit = check_output(
            ["git log -1 --date=short --pretty=format:'%cd \n├ 🛠<b>From</b> %cr'"],
            shell=True,
        ).decode()
    else:
        last_commit = "No UPSTREAM_REPO"
    currentTime = get_readable_time(time() - botStartTime)
    current = now.strftime("%m/%d %I:%M:%S %p")
    osUptime = get_readable_time(time() - boot_time())
    total, used, free, disk = disk_usage("/")
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(net_io_counters().bytes_sent)
    recv = get_readable_file_size(net_io_counters().bytes_recv)
    cpuUsage = cpu_percent(interval=0.5)
    p_core = cpu_count(logical=False)
    t_core = cpu_count(logical=True)
    swap = swap_memory()
    swap_p = swap.percent
    swap_t = get_readable_file_size(swap.total)
    memory = virtual_memory()
    mem_p = memory.percent
    mem_t = get_readable_file_size(memory.total)
    mem_a = get_readable_file_size(memory.available)
    mem_u = get_readable_file_size(memory.used)
    stats = (
        f"<b>╭─《🌐 BOT STATISTICS 🌐》</b>\n"
        f"<b>│</b>\n"
        f"<b>├ 🛠 𝙲𝙾𝙼𝙼𝙸𝚃 𝙳𝙰𝚃𝙴:</b> {last_commit}\n"
        f"<b>├ 🟢 𝙾𝙽𝙻𝙸𝙽𝙴 𝚃𝙸𝙼𝙴:</b> {currentTime}\n"
        f"<b>├ 🟢 Sᴛᴀʀᴛᴇᴅ Aᴛ:</b> {current}\n"
        f"<b>├ ☠️ 𝙾𝚂 𝚄𝙿𝚃𝙸𝙼𝙴:</b> {osUptime}\n"
        f"<b>├ 💾 𝙳𝙸𝚂𝙺 𝚂𝙿𝙰𝙲𝙴:</b> {total}\n"
        f"<b>├ 📀 𝙳𝙸𝚂𝙺 𝚂𝙿𝙰𝙲𝙴 𝚄𝚂𝙴𝙳:</b> {used}\n"
        f"<b>├ 💿 𝙳𝙸𝚂𝙺 𝚂𝙿𝙰𝙲𝙴 𝙵𝚁𝙴𝙴:</b> {free}\n"
        f"<b>├ 🔺 𝚄𝙿𝙻𝙾𝙰𝙳 𝙳𝙰𝚃𝙰:</b> {sent}\n"
        f"<b>├ 🔻 𝙳𝙾𝚆𝙽𝙻𝙾𝙰𝙳 𝙳𝙰𝚃𝙰:</b> {recv}\n"
        f"<b>├ 🖥️ 𝙲𝙿𝚄 𝚄𝚂𝙰𝙶𝙴:</b> {progress_bar(cpuUsage)} {cpuUsage}%\n"
        f"<b>├ 🎮 𝚁𝙰𝙼:</b> {progress_bar(mem_p)} {mem_p}%\n"
        f"<b>├ 👸 𝙳𝙸𝚂𝙺 𝚄𝚂𝙴𝙳:</b> {progress_bar(disk)} {disk}%\n\n"
        f"<b>├ 💽 𝙿𝙷𝚈𝚂𝙸𝙲𝙰𝙻 𝙲𝙾𝚁𝙴𝚂:</b> {p_core}\n"
        f"<b>├ 🍥 𝚃𝙾𝚃𝙰𝙻 𝙲𝙾𝚁𝙴𝚂:</b> {t_core}\n"
        f"<b>├ ✳ 𝚂𝚆𝙰𝙿:</b> {swap_t}\n"
        f"<b>├ 👸 𝚂𝚆𝙰𝙿 𝚄𝚂𝙴𝙳:</b> {swap_p}%\n"
        f"<b>├ ☁ 𝚃𝙾𝚃𝙰𝙻 𝙾𝙵 𝙼𝙴𝙼𝙾𝚁𝚈:</b> {mem_t}\n"
        f"<b>├ 💃 𝙵𝚁𝙴𝙴 𝙾𝙵 𝙼𝙴𝙼𝙾𝚁𝚈:</b> {mem_a}\n"
        f"<b>╰ 👰 𝚄𝚂𝙰𝙶𝙴 𝙾𝙵 𝙼𝙴𝙼𝙾𝚁𝚈:</b> {mem_u}\n"
    )
    heroku = getHerokuDetails(HEROKU_API_KEY, HEROKU_APP_NAME)
    if heroku:
        stats += heroku

    update.effective_message.reply_photo(IMAGE_X, stats, parse_mode=ParseMode.HTML)


def start(update, context):
    buttons = ButtonMaker()
    buttons.buildbutton("😎 Master", "https://t.me/toxytech")
    buttons.buildbutton("🙋 Mirror Group", "https://t.me/dipeshmirror")
    buttons.buildbutton("🇮🇳 Support Group", "https://t.me/mirrorsociety")
    reply_markup = InlineKeyboardMarkup(buttons.build_menu(2))
    if CustomFilters.authorized_user(update) or CustomFilters.authorized_chat(update):
        start_string = f"""
This bot can mirror all your links to Google Drive And Leech Files To Telegram!
Type /{BotCommands.HelpCommand} to get a list of available commands
"""
        sendMarkup(start_string, context.bot, update.message, reply_markup)
    else:
        sendMarkup(
            "Not Authorized user, deploy your own mirror-leech bot",
            context.bot,
            update.message,
            reply_markup,
        )


def restart(update, context):
    restart_message = sendMessage("Restarting...", context.bot, update.message)
    if Interval:
        Interval[0].cancel()
        Interval.clear()
    alive.kill()
    clean_all()
    srun(["pkill", "-9", "-f", "gunicorn|extra-api|last-api|megasdkrest"])
    srun(["python3", "update.py"])
    with open(".restartmsg", "w") as f:
        f.truncate(0)
        f.write(f"{restart_message.chat.id}\n{restart_message.message_id}\n")
    osexecl(executable, executable, "-m", "bot")


def ping(update, context):
    start_time = int(round(time() * 1000))
    reply = sendMessage("Starting Ping", context.bot, update.message)
    end_time = int(round(time() * 1000))
    editMessage(f"{end_time - start_time} ms", reply)


def log(update, context):
    sendLogFile(context.bot, update.message)


help_string = f"""
NOTE: Try each command without any perfix to see more detalis.
/{BotCommands.MirrorCommand[0]} or /{BotCommands.MirrorCommand[1]}: Start mirroring to Google Drive.
/{BotCommands.ZipMirrorCommand[0]} or /{BotCommands.ZipMirrorCommand[1]}: Start mirroring and upload the file/folder compressed with zip extension.
/{BotCommands.UnzipMirrorCommand[0]} or /{BotCommands.UnzipMirrorCommand[1]}: Start mirroring and upload the file/folder extracted from any archive extension.
/{BotCommands.QbMirrorCommand[0]} or /{BotCommands.QbMirrorCommand[1]}: Start Mirroring to Google Drive using qBittorrent.
/{BotCommands.QbZipMirrorCommand[0]} or /{BotCommands.QbZipMirrorCommand[1]}: Start mirroring using qBittorrent and upload the file/folder compressed with zip extension.
/{BotCommands.QbUnzipMirrorCommand[0]} or /{BotCommands.QbUnzipMirrorCommand[1]}: Start mirroring using qBittorrent and upload the file/folder extracted from any archive extension.
/{BotCommands.YtdlCommand[0]} or /{BotCommands.YtdlCommand[1]}: Mirror yt-dlp supported link.
/{BotCommands.YtdlZipCommand[0]} or /{BotCommands.YtdlZipCommand[1]}: Mirror yt-dlp supported link as zip.
/{BotCommands.LeechCommand[0]} or /{BotCommands.LeechCommand[1]}: Start leeching to Telegram.
/{BotCommands.ZipLeechCommand[0]} or /{BotCommands.ZipLeechCommand[1]}: Start leeching and upload the file/folder compressed with zip extension.
/{BotCommands.UnzipLeechCommand[0]} or /{BotCommands.UnzipLeechCommand[1]}: Start leeching and upload the file/folder extracted from any archive extension.
/{BotCommands.QbLeechCommand[0]} or /{BotCommands.QbLeechCommand[1]}: Start leeching using qBittorrent.
/{BotCommands.QbZipLeechCommand[0]} or /{BotCommands.QbZipLeechCommand[1]}: Start leeching using qBittorrent and upload the file/folder compressed with zip extension.
/{BotCommands.QbUnzipLeechCommand[0]} or /{BotCommands.QbUnzipLeechCommand[1]}: Start leeching using qBittorrent and upload the file/folder extracted from any archive extension.
/{BotCommands.YtdlLeechCommand[0]} or /{BotCommands.YtdlLeechCommand[1]}: Leech yt-dlp supported link.
/{BotCommands.YtdlZipLeechCommand[0]} or /{BotCommands.YtdlZipLeechCommand[1]}: Leech yt-dlp supported link as zip.
/{BotCommands.CloneCommand} [drive_url]: Copy file/folder to Google Drive.
/{BotCommands.CountCommand} [drive_url]: Count file/folder of Google Drive.
/{BotCommands.DeleteCommand} [drive_url]: Delete file/folder from Google Drive (Only Owner & Sudo).
/{BotCommands.LeechSetCommand} [query]: Leech settings.
/{BotCommands.SetThumbCommand}: Reply photo to set it as Thumbnail.
/{BotCommands.BtSelectCommand}: Select files from torrents by gid or reply.
/{BotCommands.RssListCommand[0]} or /{BotCommands.RssListCommand[1]}: List all subscribed rss feed info (Only Owner & Sudo).
/{BotCommands.RssGetCommand[0]} or /{BotCommands.RssGetCommand[1]}: Force fetch last N links (Only Owner & Sudo).
/{BotCommands.RssSubCommand[0]} or /{BotCommands.RssSubCommand[1]}: Subscribe new rss feed (Only Owner & Sudo).
/{BotCommands.RssUnSubCommand[0]} or /{BotCommands.RssUnSubCommand[1]}: Unubscribe rss feed by title (Only Owner & Sudo).
/{BotCommands.RssSettingsCommand[0]} or /{BotCommands.RssSettingsCommand[1]} [query]: Rss Settings (Only Owner & Sudo).
/{BotCommands.CancelMirror}: Cancel task by gid or reply.
/{BotCommands.CancelAllCommand} [query]: Cancel all [status] tasks.
/{BotCommands.ListCommand} [query]: Search in Google Drive(s).
/{BotCommands.SearchCommand} [query]: Search for torrents with API.
/{BotCommands.StatusCommand}: Shows a status of all the downloads.
/{BotCommands.StatsCommand}: Show stats of the machine where the bot is hosted in.
/{BotCommands.PingCommand}: Check how long it takes to Ping the Bot (Only Owner & Sudo).
/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UnAuthorizeCommand}: Unauthorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.AuthorizedUsersCommand}: Show authorized users (Only Owner & Sudo).
/{BotCommands.AddSudoCommand}: Add sudo user (Only Owner).
/{BotCommands.RmSudoCommand}: Remove sudo users (Only Owner).
/{BotCommands.RestartCommand}: Restart and update the bot (Only Owner & Sudo).
/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports (Only Owner & Sudo).
/{BotCommands.ShellCommand}: Run shell commands (Only Owner).
/{BotCommands.EvalCommand}: Run Python Code Line | Lines (Only Owner).
/{BotCommands.ExecCommand}: Run Commands In Exec (Only Owner).
/{BotCommands.ClearLocalsCommand}: Clear {BotCommands.EvalCommand} or {BotCommands.ExecCommand} locals (Only Owner).
"""


def bot_help(update, context):
    sendMessage(help_string, context.bot, update.message)


if SET_BOT_COMMANDS:
    botcmds = [
        f"{BotCommands.MirrorCommand}", "Mirror",
        f"{BotCommands.ZipMirrorCommand}", "Mirror and upload as zip",
        f"{BotCommands.UnzipMirrorCommand}", "Mirror and extract files",
        f"{BotCommands.QbMirrorCommand}", "Mirror torrent using qBittorrent",
        f"{BotCommands.QbZipMirrorCommand}","Mirror torrent and upload as zip using qb",
        f"{BotCommands.QbUnzipMirrorCommand}","Mirror torrent and extract files using qb",
        f"{BotCommands.YtdlCommand}", "Mirror yt-dlp supported link",
        f"{BotCommands.YtdlZipCommand}", "Mirror yt-dlp supported link as zip",
        f"{BotCommands.CloneCommand}", "Copy file/folder to Drive",
        f"{BotCommands.LeechCommand}", "Leech",
        f"{BotCommands.ZipLeechCommand}", "Leech and upload as zip",
        f"{BotCommands.UnzipLeechCommand}", "Leech and extract files",
        f"{BotCommands.QbLeechCommand}", "Leech torrent using qBittorrent",
        f"{BotCommands.QbZipLeechCommand}","Leech torrent and upload as zip using qb",
        f"{BotCommands.QbUnzipLeechCommand}", "Leech torrent and extract using qb",
        f"{BotCommands.YtdlLeechCommand}", "Leech yt-dlp supported link",
        f"{BotCommands.YtdlZipLeechCommand}", "Leech yt-dlp supported link as zip",
        f"{BotCommands.CountCommand}", "Count file/folder of Drive",
        f"{BotCommands.DeleteCommand}", "Delete file/folder from Drive",
        f"{BotCommands.CancelMirror}", "Cancel a task",
        f"{BotCommands.CancelAllCommand}", "Cancel all downloading tasks",
        f"{BotCommands.ListCommand}", "Search in Drive",
        f"{BotCommands.LeechSetCommand}", "Leech settings",
        f"{BotCommands.SetThumbCommand}", "Set thumbnail",
        f"{BotCommands.StatusCommand}", "Get mirror status message",
        f"{BotCommands.StatsCommand}", "Bot usage stats",
        f"{BotCommands.UsageCommand}", "Heroku Dyno usage",
        f"{BotCommands.SpeedCommand}", "Speedtest",
        f"{BotCommands.WayBackCommand}", "Internet Archive",
        f"{BotCommands.PingCommand}", "Ping the bot",
        f"{BotCommands.RestartCommand}", "Restart the bot",
        f"{BotCommands.LogCommand}", "Get the bot Log",
        f"{BotCommands.HelpCommand}", "Get detailed help",
        f"{BotCommands.AuthorizedUsersCommand}", "Authorized Users/Chats",
        f"{BotCommands.AuthorizeCommand}", "Authorize user/chat",
        f"{BotCommands.UnAuthorizeCommand}", "UnAuthorize user/chat",
        f"{BotCommands.AddSudoCommand}", "Add Sudo",
        f"{BotCommands.RmSudoCommand}", "Remove Sudo",
    ]


def main():
    start_cleanup()
    notifier_dict = False
    if INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
        if notifier_dict := DbManger().get_incomplete_tasks():
            for cid, data in notifier_dict.items():
                if ospath.isfile(".restartmsg"):
                    with open(".restartmsg") as f:
                        chat_id, msg_id = map(int, f)
                    msg = "💥𝐁𝐨𝐭 𝐒𝐭𝐚𝐫𝐭𝐞𝐝❗"
                else:
                    msg = "💥𝐁𝐨𝐭 𝐒𝐭𝐚𝐫𝐭𝐞𝐝❗"
                for tag, links in data.items():
                    msg += f"\n\n{tag}: "
                    for index, link in enumerate(links, start=1):
                        msg += f" <a href='{link}'>{index}</a> |"
                        if len(msg.encode()) > 4000:
                            if "Restarted Successfully!" in msg and cid == chat_id:
                                bot.editMessageText(
                                    msg,
                                    chat_id,
                                    msg_id,
                                    parse_mode="HTMl",
                                    disable_web_page_preview=True,
                                )
                                osremove(".restartmsg")
                            else:
                                try:
                                    bot.sendMessage(
                                        cid, msg, "HTML", disable_web_page_preview=True
                                    )
                                except Exception as e:
                                    LOGGER.error(e)
                            msg = ""
                if "Restarted Successfully!" in msg and cid == chat_id:
                    bot.editMessageText(
                        msg,
                        chat_id,
                        msg_id,
                        parse_mode="HTMl",
                        disable_web_page_preview=True,
                    )
                    osremove(".restartmsg")
                else:
                    try:
                        bot.sendMessage(cid, msg, "HTML", disable_web_page_preview=True)
                    except Exception as e:
                        LOGGER.error(e)

    if ospath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
        bot.edit_message_text("Restarted Successfully!", chat_id, msg_id)
        osremove(".restartmsg")
    elif not notifier_dict and AUTHORIZED_CHATS:
        for id_ in AUTHORIZED_CHATS:
            try:
                bot.sendMessage(id_, "Bot Restarted!", "HTML")
            except Exception as e:
                LOGGER.error(e)

    start_handler = CommandHandler(BotCommands.StartCommand, start, run_async=True)
    ping_handler = CommandHandler(
        BotCommands.PingCommand,
        ping,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True,
    )
    restart_handler = CommandHandler(
        BotCommands.RestartCommand,
        restart,
        filters=CustomFilters.owner_filter | CustomFilters.sudo_user,
        run_async=True,
    )
    help_handler = CommandHandler(
        BotCommands.HelpCommand,
        bot_help,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True,
    )
    stats_handler = CommandHandler(
        BotCommands.StatsCommand,
        stats,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True,
    )
    log_handler = CommandHandler(
        BotCommands.LogCommand,
        log,
        filters=CustomFilters.owner_filter | CustomFilters.sudo_user,
        run_async=True,
    )
    usage_handler = CommandHandler(
        BotCommands.UsageCommand,
        usage,
        filters=CustomFilters.owner_filter,
        run_async=True,
    )
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(ping_handler)
    dispatcher.add_handler(usage_handler)
    dispatcher.add_handler(restart_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(stats_handler)
    dispatcher.add_handler(log_handler)
    updater.start_polling(drop_pending_updates=IGNORE_PENDING_REQUESTS)
    LOGGER.info("💥𝐁𝐨𝐭 𝐒𝐭𝐚𝐫𝐭𝐞𝐝❗")
    signal(SIGINT, exit_clean_up)


app.start()
main()

main_loop.run_forever()
