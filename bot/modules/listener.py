from requests import utils as rutils
from re import search as re_search
from time import sleep
from os import path as ospath, remove as osremove, listdir, walk
from subprocess import Popen
from html import escape
from telegram import InlineKeyboardMarkup, ParseMode, InlineKeyboardButton

from bot import *
from bot.helper.ext_utils.bot_utils import is_url, is_magnet, is_gdtot_link, is_mega_link, is_gdrive_link, get_content_type, get_readable_time, secondsToText
from bot.helper.ext_utils.fs_utils import get_base_name, get_path_size, split_file, clean_download, clean_target
from bot.helper.ext_utils.exceptions import NotSupportedExtractionArchive
from bot.helper.mirror_utils.status_utils.extract_status import ExtractStatus
from bot.helper.mirror_utils.status_utils.zip_status import ZipStatus
from bot.helper.mirror_utils.status_utils.split_status import SplitStatus
from bot.helper.mirror_utils.status_utils.upload_status import UploadStatus
from bot.helper.mirror_utils.status_utils.tg_upload_status import TgUploadStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.shortenurl import short_url
from bot.helper.mirror_utils.upload_utils.pyrogramEngine import TgUploader
from bot.helper.telegram_helper.message_utils import auto_delete_upload_message, auto_delete_message, sendMessage, sendMarkup, delete_all_messages, update_all_messages
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger


class MirrorLeechListener:
    def __init__(
            self,
            bot,
            message,
            isZip=False,
            extract=False,
            isQbit=False,
            isLeech=False,
            pswd=None,
            tag=None,
            select=False,
            seed=False):
        self.bot = bot
        self.message = message
        self.uid = message.message_id
        self.extract = extract
        self.isZip = isZip
        self.isQbit = isQbit
        self.isLeech = isLeech
        self.pswd = pswd
        self.tag = tag
        self.seed = seed
        self.newDir = ""
        self.dir = f"{DOWNLOAD_DIR}{self.uid}"
        self.select = select
        self.elapsed_time = time()
        self.isPrivate = self.message.chat.type in ['private', 'group']
        self.user_id = self.message.from_user.id
        self.message.reply_to_message
        self.suproc = None

    def clean(self):
        try:
            Interval[0].cancel()
            Interval.clear()
            aria2.purge()
            delete_all_messages()
        except BaseException:
            pass

    def onDownloadStart(self):
        if not self.isPrivate and INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
            DbManger().add_incomplete_task(self.message.chat.id, self.message.link, self.tag)

    def onDownloadComplete(self):
        with download_dict_lock:
            LOGGER.info(f"Download completed: {download_dict[self.uid].name()}")
            download = download_dict[self.uid]
            name = str(download.name()).replace('/', '')
            gid = download.gid()
            if name == "None" or self.isQbit or not ospath.exists(f'{DOWNLOAD_DIR}{self.uid}/{name}'):
                name = listdir(f'{DOWNLOAD_DIR}{self.uid}')[-1]
            m_path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        size = get_path_size(m_path)
        if self.isZip:
            path = f"{m_path}.zip"
            with download_dict_lock:
                download_dict[self.uid] = ZipStatus(name, size, gid, self, self.message)
            if self.pswd is not None:
                if self.isLeech and int(size) > LEECH_SPLIT_SIZE:
                    LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}.0*')
                    self.suproc = Popen(["7z", f"-v{MAX_SPLIT_SIZE}b", "a", "-mx=0", f"-p{self.pswd}", path, m_path])
                else:
                    LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}')
                    self.suproc = Popen(["7z", "a", "-mx=0", f"-p{self.pswd}", path, m_path])
            elif self.isLeech and int(size) > LEECH_SPLIT_SIZE:
                LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}.0*')
                self.suproc = Popen(["7z", f"-v{MAX_SPLIT_SIZE}b", "a", "-mx=0", path, m_path])
            else:
                LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}')
                self.suproc = Popen(["7z", "a", "-mx=0", path, m_path])
            self.suproc.wait()
            if self.suproc.returncode == -9:
                return
            elif self.suproc.returncode != 0:
                LOGGER.error('An error occurred while zipping! Uploading anyway')
                path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
            if self.suproc.returncode == 0 and (not self.isQbit or not self.seed or self.isLeech):
                try:
                    rmtree(m_path)
                except:
                    osremove(m_path)
        elif self.extract:
            try:
                if ospath.isfile(m_path):
                    path = get_base_name(m_path)
                LOGGER.info(f"Extracting: {name}")
                with download_dict_lock:
                    download_dict[self.uid] = ExtractStatus(name, size, gid, self, self.message)
                if ospath.isdir(m_path):
                    for dirpath, subdir, files in walk(m_path, topdown=False):
                        for file_ in files:
                            if file_.endswith((".zip", ".7z")) or re_search(r'\.part0*1\.rar$|\.7z\.0*1$|\.zip\.0*1$', file_) \
                                   or (file_.endswith(".rar") and not re_search(r'\.part\d+\.rar$', file_)):
                                m_path = ospath.join(dirpath, file_)
                                if self.pswd is not None:
                                    self.suproc = Popen(["7z", "x", f"-p{self.pswd}", m_path, f"-o{dirpath}", "-aot"])
                                else:
                                    self.suproc = Popen(["7z", "x", m_path, f"-o{dirpath}", "-aot"])
                                self.suproc.wait()
                                if self.suproc.returncode == -9:
                                    return
                                elif self.suproc.returncode != 0:
                                    LOGGER.error('Unable to extract archive splits! Uploading anyway')
                        if self.suproc is not None and self.suproc.returncode == 0:
                            for file_ in files:
                                if file_.endswith((".rar", ".zip", ".7z")) or \
                                        re_search(r'\.r\d+$|\.7z\.\d+$|\.z\d+$|\.zip\.\d+$', file_):
                                    del_path = ospath.join(dirpath, file_)
                                    osremove(del_path)
                    path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
                else:
                    if self.pswd is not None:
                        self.suproc = Popen(["bash", "pextract", m_path, self.pswd])
                    else:
                        self.suproc = Popen(["bash", "extract", m_path])
                    self.suproc.wait()
                    if self.suproc.returncode == -9:
                        return
                    elif self.suproc.returncode == 0:
                        LOGGER.info(f"Extracted Path: {path}")
                        osremove(m_path)
                    else:
                        LOGGER.error('Unable to extract archive! Uploading anyway')
                        path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
            except NotSupportedExtractionArchive:
                LOGGER.info("Not any valid archive, uploading file as it is.")
                path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        else:
            path = f'{DOWNLOAD_DIR}{self.uid}/{name}'
        up_dir, up_name = path.rsplit('/', 1)
        if self.isLeech and not self.isZip:
            checked = False
            for dirpath, subdir, files in walk(f'{DOWNLOAD_DIR}{self.uid}', topdown=False):
                for file_ in files:
                    f_path = ospath.join(dirpath, file_)
                    f_size = ospath.getsize(f_path)
                    if int(f_size) > MAX_SPLIT_SIZE:
                        if not checked:
                            checked = True
                            with download_dict_lock:
                                download_dict[self.uid] = SplitStatus(up_name, size, gid, self, self.message)
                            LOGGER.info(f"Splitting: {up_name}")
                        if res := split_file(
                            f_path, f_size, file_, dirpath, TG_SPLIT_SIZE, self
                        ):
                            osremove(f_path)
                        else:
                            return
        if self.isLeech:
            up_path = f'{DOWNLOAD_DIR}{self.uid}'
            size = get_path_size(f'{DOWNLOAD_DIR}{self.uid}')
            LOGGER.info(f"Leech Name: {up_name}")
            tg = TgUploader(up_name, self)
            tg_upload_status = TgUploadStatus(tg, size, gid, self)
            with download_dict_lock:
                download_dict[self.uid] = tg_upload_status
            update_all_messages()
            tg.upload()
        else:
            up_path = f'{DOWNLOAD_DIR}{self.uid}'
            size = get_path_size(up_path)
            LOGGER.info(f"Upload Name: {up_name}")
            drive = GoogleDriveHelper(up_name, up_dir, size, self)
            upload_status = UploadStatus(drive, size, gid, self)
            with download_dict_lock:
                download_dict[self.uid] = upload_status
            update_all_messages()
            drive.upload(up_name)

    def onUploadComplete(self, link: str, size, files, folders, typ, name):
        buttons = ButtonMaker()
        mesg = self.message.text.split('\n')
        message_args = mesg[0].split(' ', maxsplit=1)
        reply_to = self.message.reply_to_message
        slmsg = f"Added by: {self.tag} \n👥 User ID: <code>{self.user_id}</code>\n\n"
        if LINK_LOGS:
            try:
                source_link = message_args[1]
                for link_log in LINK_LOGS:
                    bot.sendMessage(
                        link_log,
                        text=slmsg + source_link,
                        parse_mode=ParseMode.HTML)
            except IndexError:
                pass
            if reply_to is not None:
                try:
                    reply_text = reply_to.text
                    if is_url(reply_text):
                        source_link = reply_text.strip()
                        for link_log in LINK_LOGS:
                            bot.sendMessage(
                                chat_id=link_log,
                                text=slmsg + source_link,
                                parse_mode=ParseMode.HTML)
                except TypeError:
                    pass
        if AUTO_DELETE_UPLOAD_MESSAGE_DURATION != -1:
            reply_to = self.message.reply_to_message
            if reply_to is not None:
                try:
                    Thread(
                        target=auto_delete_reply_message, args=(self.bot, self.message)
                    ).start()
                except Exception as error:
                    LOGGER.warning(error)
            if self.message.chat.type == "private":
                warnmsg = ""
            else:
                autodel = secondsToText()
                warnmsg = f"\n𝐓𝐡𝐢𝐬 𝐌𝐞𝐬𝐬𝐚𝐠𝐞 𝐖𝐢𝐥𝐥 𝐀𝐮𝐭𝐨 𝐃𝐞𝐥𝐞𝐭𝐞𝐝 𝐈𝐧 {autodel} 𝐌𝐢𝐧𝐮𝐭𝐞𝐬\n\n"
        else:
            warnmsg = ""
        if BOT_PM and self.message.chat.type != 'private':
            pmwarn = f"<b>I have sent files in PM.</b>\n"
        elif self.message.chat.type == 'private':
            pmwarn = ''
        else:
            pmwarn = ''
        if MIRROR_LOGS and self.message.chat.type != 'private':
            logwarn = f"<b>I have sent files in Mirror Log Channel.(Join Mirror Log channel) </b>\n"
        elif self.message.chat.type == 'private':
            logwarn = ''
        else:
            logwarn = ''
        if LEECH_LOG and self.message.chat.type != 'private':
            logleechwarn = f"<b>I have sent files in Leech Log Channel.(Join Leech Log channel) </b>\n"
        elif self.message.chat.type == 'private':
            logleechwarn = ''
        else:
            logleechwarn = ''
        if not self.isPrivate and INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
            DbManger().rm_complete_task(self.message.link)
        msg = f"<b>╭Name: </b><code>{escape(name)}</code>\n<b>├Size: </b>{size}"
        if self.isLeech:
            if SOURCE_LINK is True:
                try:
                    source_link = message_args[1]
                    if is_magnet(source_link):
                        link = telegraph.create_page(
                            title='ReflectionMirror Source Link',
                            content=source_link,
                        )["path"]
                        buttons.buildbutton(
                            f"🔗 Source Link", f"https://telegra.ph/{link}")
                    else:
                        buttons.buildbutton(f"🔗 Source Link", source_link)
                except Exception:
                    pass
                if reply_to is not None:
                    try:
                        reply_text = reply_to.text
                        if is_url(reply_text):
                            source_link = reply_text.strip()
                            if is_magnet(source_link):
                                link = telegraph.create_page(
                                    title='WeebZone Source Link',
                                    content=source_link,
                                )["path"]
                                buttons.buildbutton(
                                    f"🔗 Source Link", f"https://telegra.ph/{link}")
                            else:
                                buttons.buildbutton(
                                    f"🔗 Source Link", source_link)
                    except Exception:
                        pass
            msg += f'\n<b>├Total Files: </b>{folders}'
            if typ != 0:
                msg += f'\n<b>├Corrupted Files: </b>{typ}'
            msg += f'\n<b>├It Tooks:</b> {get_readable_time(time() - self.message.date.timestamp())}'
            msg += f'\n<b>├cc: </b>{self.tag}'
            msg += f'\n<b>╰Thanks For using {TITLE_NAME}</b>\n'
            if not files:
                reply_message = sendMarkup(
                    msg,
                    self.bot,
                    self.message,
                    InlineKeyboardMarkup(buttons.build_menu(2)),
                )
            else:
                if BOT_PM and self.message.chat.type != "private":
                    pmwarn_leech = f"\n 𝐈 𝐇𝐚𝐯𝐞 𝐒𝐞𝐧𝐭 𝐅𝐢𝐥𝐞𝐬 𝐈𝐧 𝐁𝐨𝐭 𝐏𝐌."
                    try:
                        replymsg = bot.sendMessage(
                            chat_id=self.user_id,
                            text=msg,
                            reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)),
                            parse_mode=ParseMode.HTML,
                        )
                        buttons.sbutton(
                            "Vɪᴇᴡ Fɪʟᴇ ɪɴ PM",
                            f"botpmfilebutton {self.user_id} {replymsg.message_id}",
                        )
                    except Exception as e:
                        LOGGER.warning(f"Unable to send message to PM: {str(e)}")
                elif self.message.chat.type == "private":
                    pmwarn_leech = ""
                else:
                    pmwarn_leech = ""
                if LEECH_LOG and self.message.chat.type != "private":
                    for i in LEECH_LOG:
                        try:
                            fmsg = ""
                            for index, (link, name) in enumerate(
                                files.items(), start=1
                            ):
                                fmsg += f"{index}. <a href='{link}'>{name}</a>\n"
                                if len(fmsg.encode() + msg.encode()) > 4000:
                                    sleep(1)
                                    replymsg = bot.sendMessage(
                                        chat_id=i,
                                        text=msg + fmsg,
                                        reply_markup=InlineKeyboardMarkup(
                                            buttons.build_menu(2)
                                        ),
                                        parse_mode=ParseMode.HTML,
                                    )
                                    fmsg = ""
                            if fmsg != "":
                                sleep(1)
                                replymsg = bot.sendMessage(
                                    chat_id=i,
                                    text=msg + fmsg,
                                    reply_markup=InlineKeyboardMarkup(
                                        buttons.build_menu(2)
                                    ),
                                    parse_mode=ParseMode.HTML,
                                )
                            if self.message.chat_id != i:
                                try:
                                    log_channel = LEECH_LOG_CHANNEL_LINK
                                    leech_chat_id = str(LEECH_LOG)[5:][:-1]
                                    leech_file = f"https://t.me/c/{leech_chat_id}/{replymsg.message_id}"
                                    logwarn_leech = f'\n 𝐈 𝐇𝐚𝐯𝐞 𝐒𝐞𝐧𝐭 𝐅𝐢𝐥𝐞𝐬 𝐈𝐧  <a href="{log_channel}">#Leech 𝐋𝐨𝐠𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥</a>.'
                                    logwarn_leech += f'\n 𝐉𝐨𝐢𝐧 𝐓𝐡𝐞 𝐂𝐡𝐚𝐧𝐧𝐞𝐥 𝐔𝐬𝐢𝐧𝐠 𝐓𝐡𝐞 𝐀𝐛𝐨𝐯𝐞 𝐋𝐢𝐧𝐤 𝐓𝐨 𝐒𝐞𝐞 <a href="{leech_file}">#Leeched Files</a>.'
                                except Exception as ex:
                                    LOGGER.warning(
                                        f"Error in logwarn_leech string : {str(ex)}"
                                    )
                                    logwarn_leech = "\n I Have Sent Files In #Leech Logs Channel</a>."
                            else:
                                logwarn_leech = ""
                        except Exception as e:
                            LOGGER.warning(f"Error with Leech Logs Message: {str(e)}")
                elif self.message.chat.type == "private":
                    logwarn_leech = ""
                else:
                    logwarn_leech = ""
                reply_message = sendMarkup(
                    msg + pmwarn_leech + logwarn_leech + warnmsg,
                    self.bot,
                    self.message,
                    InlineKeyboardMarkup(buttons.build_menu(2)),
                )
            Thread(
                target=auto_delete_upload_message,
                args=(bot, self.message, reply_message),
            ).start()
        else:
            msg += f'\n<b>├Type: </b>{typ}'
            if ospath.isdir(f'{DOWNLOAD_DIR}{self.uid}/{name}'):
                msg += f'\n<b>├SubFolders: </b>{folders}'
                msg += f'\n<b>├Files: </b>{files}'
            msg += f'\n<b>├It Tooks:</b> {get_readable_time(time() - self.message.date.timestamp())}'
            msg += f'\n<b>├cc: </b>{self.tag}'
            msg += f'\n<b>╰Thanks For using {TITLE_NAME}</b>\n'
            buttons = ButtonMaker()
            link = short_url(link)
            buttons.buildbutton("🔓 Drive Link", link)
            LOGGER.info(f'Done Uploading {name}')
            if INDEX_URL is not None:
                url_path = rutils.quote(f'{name}')
                share_url = f'{INDEX_URL}/{url_path}'
                if ospath.isdir(f'{DOWNLOAD_DIR}/{self.uid}/{name}'):
                    share_url += '/'
                    share_url = short_url(share_url)
                    buttons.buildbutton("🚀 Index Link", share_url)
                else:
                    share_url = short_url(share_url)
                    buttons.buildbutton("🚀 Index Link", share_url)
                    if VIEW_LINK:
                        share_urls = f'{INDEX_URL}/{url_path}?a=view'
                        share_urls = short_url(share_urls)
                        buttons.buildbutton("🌐 View Link", share_urls)
            if BUTTON_FOUR_NAME is not None and BUTTON_FOUR_URL is not None:
                buttons.buildbutton(
                    f"{BUTTON_FOUR_NAME}",
                    f"{BUTTON_FOUR_URL}")
            if BUTTON_FIVE_NAME is not None and BUTTON_FIVE_URL is not None:
                buttons.buildbutton(
                    f"{BUTTON_FIVE_NAME}",
                    f"{BUTTON_FIVE_URL}")
            if BUTTON_SIX_NAME is not None and BUTTON_SIX_URL is not None:
                buttons.buildbutton(f"{BUTTON_SIX_NAME}", f"{BUTTON_SIX_URL}")
            if SOURCE_LINK is True:
                try:
                    mesg = message_args[1]
                    if is_magnet(mesg):
                        link = telegraph.create_page(
                            title='ReflectionMirror Source Link',
                            content=mesg,
                        )["path"]
                        buttons.buildbutton(
                            f"🔗 Source Link", f"https://telegra.ph/{link}")
                    elif is_url(mesg):
                        source_link = mesg
                        if source_link.startswith(("|", "pswd: ")):
                            pass
                        else:
                            buttons.buildbutton(f"🔗 Source Link", source_link)
                    else:
                        pass
                except Exception:
                    pass
            if reply_to is not None:
                try:
                    reply_text = reply_to.text
                    if is_url(reply_text):
                        source_link = reply_text.strip()
                        if is_magnet(source_link):
                            link = telegraph.create_page(
                                title='WeebZone Source Link',
                                content=source_link,
                            )["path"]
                            buttons.buildbutton(
                                f"🔗 Source Link", f"https://telegra.ph/{link}")
                        else:
                            buttons.buildbutton(f"🔗 Source Link", source_link)
                except Exception:
                    pass
            else:
                pass
            if BOT_PM and self.message.chat.type != "private":
                pmwarn_mirror = f"\n𝐈 𝐇𝐚𝐯𝐞 𝐒𝐞𝐧𝐭 𝐅𝐢𝐥𝐞𝐬 𝐈𝐧 𝐁𝐎𝐓 𝐏𝐌."
                try:
                    replymsg = bot.sendMessage(
                        chat_id=self.user_id,
                        text=msg,
                        reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)),
                        parse_mode=ParseMode.HTML,
                    )
                    buttons.sbutton(
                        "Vɪᴇᴡ Fɪʟᴇ ɪɴ PM",
                        f"botpmfilebutton {self.user_id} {replymsg.message_id}",
                    )
                except Exception as e:
                    LOGGER.warning(f"Unable to send files to PM: {str(e)}")
            elif self.message.chat.type == "private":
                pmwarn_mirror = ""
            else:
                pmwarn_mirror = ""
            if MIRROR_LOGS and self.message.chat.type != "private":
                for i in MIRROR_LOGS:
                    try:
                        replymsg = bot.sendMessage(
                            chat_id=i,
                            text=msg,
                            reply_markup=InlineKeyboardMarkup(buttons.build_menu(2)),
                            parse_mode=ParseMode.HTML,
                        )
                        if self.message.chat_id != i:
                            try:
                                log_channel = MIRROR_LOGS_CHANNEL_LINK
                                mirror_chat_id = str(MIRROR_LOGS)[5:][:-1]
                                mirror_file = f"https://t.me/c/{mirror_chat_id}/{replymsg.message_id}"
                                logwarn_mirror = f'\n𝐈 𝐇𝐚𝐯𝐞 𝐒𝐞𝐧𝐭 𝐅𝐢𝐥𝐞𝐬 𝐈𝐧 <a href="{log_channel}">#Mirror/Clone 𝐋𝐨𝐠𝐬 𝐂𝐡𝐚𝐧𝐧𝐞𝐥</a>.'
                                logwarn_mirror += f'\n𝐉𝐨𝐢𝐧 𝐓𝐡𝐞 𝐂𝐡𝐚𝐧𝐧𝐞𝐥 𝐔𝐬𝐢𝐧𝐠 𝐓𝐡𝐞 𝐀𝐛𝐨𝐯𝐞 𝐋𝐢𝐧𝐤 𝐓𝐨 𝐒𝐞𝐞 <a href="{mirror_file}">#Mirrored Files</a>.'
                            except Exception as ex:
                                LOGGER.warning(
                                    f"Error in logwarn_mirror message: {str(ex)}"
                                )
                                logwarn_mirror = "\n I Have Sent Files In #Mirror/Clone Logs Channel</a>."
                    except Exception as e:
                        LOGGER.warning(f"Unable to send files to Mirror Logs: {str(e)}")
            elif self.message.chat.type == "private":
                logwarn_mirror = ""
            else:
                logwarn_mirror = ""
            reply_message = sendMarkup(
                msg + pmwarn_mirror + logwarn_mirror + warnmsg,
                self.bot,
                self.message,
                InlineKeyboardMarkup(buttons.build_menu(2)),
            )
            Thread(
                target=auto_delete_upload_message,
                args=(bot, self.message, reply_message),
            ).start()
            if self.isQbit and self.seed and not self.extract:
                if self.isZip:
                    try:
                        osremove(f"{DOWNLOAD_DIR}{self.uid}/{name}")
                    except Exception:
                        pass
                return
        clean_download(f"{DOWNLOAD_DIR}{self.uid}")
        with download_dict_lock:
            try:
                del download_dict[self.uid]
            except Exception as e:
                LOGGER.error(str(e))
            count = len(download_dict)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

    def onDownloadError(self, error):
        error = error.replace('<', ' ').replace('>', ' ')
        clean_download(self.dir)
        if self.newDir:
            clean_download(self.newDir)
        with download_dict_lock:
            try:
                del download_dict[self.uid]
            except Exception as e:
                LOGGER.error(str(e))
            count = len(download_dict)
        msg = f"⚠⁉ {self.tag}\n<b>Download has been stopped</b>\n<b>Due to: </b>{error}\n<b>Elapsed : </b>{get_readable_time(time() - self.message.date.timestamp())}"
        sendMessage(msg, self.bot, self.message)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

        if not self.isPrivate and INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
            DbManger().rm_complete_task(self.message.link)

    def onUploadError(self, error):
        e_str = error.replace('<', '').replace('>', '')
        clean_download(f'{DOWNLOAD_DIR}{self.uid}')
        with download_dict_lock:
            try:
                del download_dict[self.uid]
            except Exception as e:
                LOGGER.error(str(e))
            count = len(download_dict)
        sendMessage(f"{self.tag} {e_str}", self.bot, self.message)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

        if not self.isPrivate and INCOMPLETE_TASK_NOTIFIER and DB_URI is not None:
            DbManger().rm_complete_task(self.message.link)
