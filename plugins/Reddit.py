import os
import sqlite3
import time
import traceback

import discord
import feedparser

from util import Events
from util.Ranks import Ranks


class Plugin(object):
    def __init__(self, pm):
        self.pm = pm
        self.last_post = dict()

    @staticmethod
    def register_events():
        """
        :return: A list of util.Events
        """
        return [Events.Loop("reddit_check"),
                Events.Command("reddit", Ranks.Admin)]

    async def handle_command(self, message_object, command, args):
        """
        :param message_object: discord.Message object containing the message
        :param command: The name of the command (first word in the message, without prefix)
        :param args: List of words in the message
        """
        if command == "reddit":
            await self.enable_notification(message_object, args[1])

    async def handle_loop(self):
        for server in self.pm.client.servers:

            # Get subreddits to be checked
            # Connect to SQLite file for server in cache/SERVERID.sqlite
            if not os.path.exists("cache/"):
                os.mkdir("cache/")
            con = sqlite3.connect("cache/" + server.id + ".sqlite",
                                  detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            subreddits = list()
            try:
                with con:
                    cur = con.cursor()
                    cur.execute("SELECT * FROM reddit_notification")
                    rows = cur.fetchall()
                    for row in rows:
                        subreddits.append({"channel": row[0], "subreddit": row[1]})
            except sqlite3.OperationalError:
                continue

            # Check all active notification subscriptions for this server
            for subscription in subreddits:

                try:
                    d = feedparser.parse("https://www.reddit.com/r/" + subscription["subreddit"] +
                                         "/search.rss?q=ups%3A5..9999999&sort=new&restrict_sr=on&syntax=cloudsearch")

                    # If first check for this channel, init seen posts
                    if subscription["channel"] not in self.last_post:
                        # No entries seen yet, set last post as last seen but don't post anything
                        new_ids = []
                        for i in range(0, 15):
                            new_ids.insert(0, d.entries[i].id)
                        self.last_post[subscription["channel"]] = {"ids": new_ids,
                                                                   "date": time.mktime(d.entries[0].updated_parsed)}

                    for i in range(0, 10):
                        if d.entries[i].id in self.last_post[subscription["channel"]]["ids"]:
                            # Entry is still the same, don't do anything
                            continue
                        elif d.entries[i].id not in self.last_post[subscription["channel"]]["ids"]:
                            if time.mktime(d.entries[i].updated_parsed) > time.mktime(
                                    d.entries[len(d.entries)-1].updated_parsed):
                                # New post found, update last post ID and notify server
                                new_ids = self.update_ids(self.last_post[subscription["channel"]]["ids"],
                                                          d.entries[i].id)

                                self.last_post[subscription["channel"]] = {"ids": new_ids,
                                                                           "date": time.mktime(
                                                                               d.entries[i].updated_parsed)}

                                await self.pm.client.send_message(discord.Object(id=int(subscription["channel"])),
                                                                  "**New post on /r/" + subscription["subreddit"] +
                                                                  " by " + d.entries[i].author + "**\n" + d.entries[
                                                                      i].link)
                            else:
                                new_ids = self.update_ids(self.last_post[subscription["channel"]]["ids"],
                                                          d.entries[i].id)

                                self.last_post[subscription["channel"]] = {"ids": new_ids,
                                                                           "date": time.mktime(
                                                                               d.entries[i].updated_parsed)}
                except:
                    traceback.print_exc()
                    continue

    async def enable_notification(self, message_object, subreddit):
        # Connect to SQLite file for server in cache/SERVERID.sqlite
        if not os.path.exists("cache/"):
            os.mkdir("cache/")
        con = sqlite3.connect("cache/" + message_object.server.id + ".sqlite",
                              detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

        with con:
            cur = con.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS reddit_notification(Channel TEXT PRIMARY KEY, Subreddit TEXT)")
            cur.execute(
                'INSERT OR REPLACE INTO reddit_notification(Channel, Subreddit) VALUES(?,?)',
                (message_object.channel.id, subreddit))

    @staticmethod
    def update_ids(ids, new_id):
        if new_id in ids:
            return new_id
        else:
            ids.insert(0, new_id)
            return ids[:20]
