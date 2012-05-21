#!/usr/bin/env python
import cgi
import datetime
import wsgiref.handlers
try:
    import json
except:
    import simplejson as json
import string

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp

import structures

allowed_clients = ["1.7.3.0","1.7.3.2","1.7.3.6"]
allowed_versions = ["1"]


class UploadedResults(webapp.RequestHandler):
	def post(self):
		post_body = self.request.body
		
		sections = post_body.split('&')
		results = {}
		for pair in sections:
			ab = pair.split('=')
			results[ab[0]] = ab[1]
		
		client = results["client"]
		
		version = results["version"]
		if version in allowed_versions and client in allowed_clients:
			uploader = results["user"]
			
			user = structures.Uploader.get_by_key_name(uploader + "|" + client)
			if user is None:
				user = structures.Uploader(key_name = uploader + "|" + client,
				Name = uploader, Version = version, TotalUploads = 0)
			
			rumble = results["game"]
			
			
			game = structures.Rumble.get_by_key_name(rumble)
			if game is None:
				game = structures.Rumble(key_name = rumble,
				Name = rumble, Rounds = int(results["rounds"]),
				Field = results["field"], Melee = bool(results["melee"] == "YES"),
				Teams = bool(results["teams"] == "YES"), TotalUploads = 0)
				#game.put()
				self.response.out.write("OK. CREATED NEW GAME TYPE!!")
				#self.response.out.write(str(bool(results["melee"] == "YES")))
			else:
				field = game.Field == results["field"]
				rounds = (game.Rounds == int(results["rounds"]))
				teams = game.Teams == bool(results["teams"] == "YES")
				melee = game.Melee == bool(results["melee"] == "YES")
				allowed = field and rounds and teams and melee
				if not allowed:
					self.response.out.write("OK. ERROR. YOUR RUMBLE CONFIG DOES NOT MATCH RUMBLE NAME!!!")
					#self.response.out.write(str(field) + str(rounds) + str(teams) + str(melee))
					return
				
			
			
			bota = results["fname"]
			botb = results["sname"]
			pd =   [[bota , botb ,rumble , uploader], 
						[botb ,bota , rumble , uploader],
						[bota , botb , rumble , structures.total],
						[botb , bota , rumble , structures.total]]
			pairHashes = [string.join(a,"|") for a in pd]
						
			pairs = structures.Pairing.get_by_key_name(pairHashes)
			for i in [0, 1, 2, 3]:
				pair = pairs[i]
				if pair is None:
					pairs[i] = structures.Pairing(key_name = pairHashes[i],
						BotA = pd[i][0], BotB = pd[i][1], Rumble = pd[i][2],
						Uploader = pd[i][3], Battles = 0, APS = 0.0, Survival = 0.0)
				
			bd = [[bota, rumble], [botb, rumble]]
			
			botHashes = [string.join(a,"|") for a in bd]
				  
			bots = structures.BotEntry.get_by_key_name(botHashes)
			for i in [0, 1]:
				if bots[i] is None:
					bots[i] = structures.BotEntry(key_name = botHashes[i],
							Name = bd[i][0],Battles = 0, Pairings = 0, APS = 0.0,
							Survival = 0.0, PL = 0, Rumble = rumble, Active = True)			
						
			
			scorea = float(results["fscore"])
			scoreb = float(results["sscore"])
			APSa = 100*scorea/(scorea+scoreb)
			APSb = 100 - APSa
			
			survivala = float(results["fsurvival"])
			survivalb = float(results["ssurvival"])
			if survivala + survivalb > 0.0:
				survivala = 100.0*survivala/(survivala+survivalb)
				survivalb = 100.0 - survivala
			else:
				survivala = 50.0
				survivalb = 50.0
			uploaderBattles = pairs[0].Battles
			
			pairs[0].APS*= float(uploaderBattles)/(uploaderBattles + 1)
			pairs[0].APS += APSa/(uploaderBattles + 1)
			
			pairs[1].APS = 100 - pairs[0].APS
			
			pairs[0].Survival *= float(uploaderBattles)/(uploaderBattles + 1)
			pairs[0].Survival += survivala/(uploaderBattles + 1)
			
			pairs[1].Survival = 100 - pairs[0].Survival

			totalBattles = pairs[2].Battles
			botaPairs = float(bots[0].Pairings)
			botbPairs = float(bots[1].Pairings)
			if totalBattles == 0:
				bots[0].APS *= botaPairs/(botaPairs+1)
				bots[0].Survival *= botaPairs/(botaPairs+1)
				bots[1].APS *= botbPairs/(botbPairs+1)
				bots[1].Survival *= botbPairs/(botbPairs+1)
			else:
				bots[0].APS -= pairs[2].APS/botaPairs
				bots[0].Survival -= pairs[2].Survival/botaPairs
				bots[1].APS -= pairs[3].APS/botbPairs
				bots[1].Survival -= pairs[3].Survival/botbPairs
				
			
			wasLoss = pairs[2].APS < 50.0
			pairs[2].APS *= float(totalBattles)/(totalBattles + 1)
			pairs[2].APS += APSa/(totalBattles+1)
			nowLoss = pairs[2].APS < 50.0
			
			if wasLoss and not nowLoss:
				bots[0].PL += 1
				bots[1].PL -= 1
			
			pairs[3].APS = 100 - pairs[2].APS
			
			pairs[2].Survival *= float(totalBattles)/(totalBattles + 1)
			pairs[2].Survival += survivala/(totalBattles+1)
			
			pairs[3].Survival = 100 - pairs[2].Survival
			

			if totalBattles == 0:	
				bots[0].APS += pairs[2].APS/(botaPairs+1)
				bots[0].Survival += pairs[2].Survival/(botaPairs+1)
				bots[1].APS += pairs[3].APS/(botbPairs+1)
				bots[1].Survival += pairs[3].Survival/(botbPairs+1)
				
				bots[0].Pairings += 1
				bots[1].Pairings += 1
			else:
				bots[0].APS += pairs[2].APS/botaPairs
				bots[0].Survival += pairs[2].Survival/botaPairs
				bots[1].APS += pairs[3].APS/botbPairs
				bots[1].Survival += pairs[3].Survival/botbPairs
			
			

			bots[0].Battles += 1
			bots[1].Battles += 1
			pairs[0].Battles += 1
			pairs[1].Battles += 1
			pairs[2].Battles += 1
			pairs[3].Battles += 1
			user.TotalUploads += 1
			game.TotalUploads += 1
			
			bots[0].LastUpload = datetime.datetime.now()
			bots[1].LastUpload = datetime.datetime.now()
			pairs[0].LastUpload = datetime.datetime.now()
			pairs[1].LastUpload = datetime.datetime.now()
			pairs[2].LastUpload = datetime.datetime.now()
			pairs[3].LastUpload = datetime.datetime.now()
			user.LastUpload = datetime.datetime.now()
			
			
			try:
				db.put(pairs)
				db.put(bots)
				db.put(user)
				db.put(game)
			except:
				self.response.out.write("ERROR PUTTING PAIRS DATA \r\n")
			
			
			self.response.out.write("OK.")
			
		else:
			self.response.out.write("CLIENT NOT SUPPORTED")


application = webapp.WSGIApplication([
	('/UploadedResults', UploadedResults)
], debug=True)


def main():
	wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
	main()
