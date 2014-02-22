from django.db import models
import os

class pilapse_project(models.Model):
    #Project settings
    project_name = models.CharField(max_length=200)
    folder = models.CharField(max_length=200)
    keep_images=models.BooleanField(verbose_name="Keep images?", name='Keep images')

    #Timelapser settings
    brightness = models.IntegerField(verbose_name="Target brightness", name='brightness')
    interval = models.IntegerField(verbose_name="Shot interval in seconds", name='interval')
    width =  models.IntegerField(verbose_name="Image width", name='width')
    height = models.IntegerField(verbose_name="Image height", name='height')
    maxtime= models.IntegerField(verbose_name="Maximum time in minutes", name='maxtime')
    maxshots=models.IntegerField(verbose_name="Maximum shots", name='maxshots')
    delta = models.IntegerField(verbose_name="Allowed brightness variance", name='delta')
    listen=models.BooleanField(verbose_name="Listen mode?", name='listen')

    def __unicode__(self):
        return self.project_name

    def make_folder(self):
        """
        Create the project folder.
        """
        try:
            os.listdir(self.folder)
        except:
            os.mdir(self.folder)

    def validator(self):
        """
        Validate data in each of the user-defined fields.  Returns a dict of booleans
        for the results.
        """
        valid={}
        valid['brightness']=(0<=self.brightness<256)
        valid['interval']=(0<self.interval)
        valid['width']=(1<=self.width<2592)
        valid['height']=(1<=self.height<1944)
        valid['maxtime']=(-1<=self.maxtime)
        valid['maxshots']=(-1<=self.maxshots)
        valid['delta']=(0<=self.delta)
        try:
            os.listdir(self.folder)
            valid['folder']=True
        except:
            valid['folder']=False
        return valid



class timelapser(models.Model):
    """
    We construct a timelapser as a Django model.  There should be only a single instance
    in the database table; we will only ever use the first instance.
    """

    uid = models.CharField(max_length=200)
    project = models.ForeignKey(pilapse_project)
    currentss = models.IntegerField(verbose_name="Shutter Speed", name='ss')
    currentiso = models.IntegerField(verbose_name="ISO", name='iso')
    lastbr = models.IntegerField(verbose_name="Last shot brightness", name='lastbr')
    shots_taken = models.IntegerField(verbose_name="Shots taken", name='shots_taken')
    start_on_boot=models.BooleanField(verbose_name="Start on boot?", name='boot')
    active=models.BooleanField(verbose_name="Tracks whether currently taking photos", name='active')
    metersite='a'

    def __unicode__(self):
        return "Pilapser with prefix "+self.project.project_name

    def time_elapsed(self):
        return self.shots_taken*self.project.interval

    def avgbrightness(self, im):
        """
        Find the average brightness of the provided image according to the method
        defined in `self.metersite`
        """
        aa=im.convert('L')
        (h,w)=aa.size
        top=0
        bottom=h
        left=0
        right=w
        aa=aa.crop((left,top,right,bottom))
        pixels=(aa.size[0]*aa.size[1])
        h=aa.histogram()
        mu0=sum([i*h[i] for i in range(len(h))])/pixels
        return mu0

    def dynamic_adjust(self):
        """
        Applies a simple gradient descent to try to correct shutterspeed and
        brightness to match the target brightness.
        """
        targetBrightness=self.project.brightness
        delta=targetBrightness-self.lastbr
        Adj = lambda v: int( v*(1.0+delta*1.0/self.targetBrightness) )
        newss=self.currentss
        newiso=self.currentiso
        if delta<0:
            #too bright.
            if self.currentiso>self.miniso:
                #reduce iso first if possible
                newiso=Adj(self.currentiso)
                newiso=max([newiso,self.miniso])
            else:
                newss=Adj(self.currentss)
                newss=max([newss, self.minss])
        elif delta>0:
            #too dim.
            if self.currentss<self.maxss:
                #increase ss first if possible
                newss=Adj(self.currentss)
                newss=min([newss, self.maxss])
            else:
                newiso=Adj(self.currentiso)
                newiso=min([newiso,self.maxiso])
        self.currentss=newss
        self.currentiso=newiso

    def findinitialparams(self):
        """
        Take a number of small shots in succession to determine a shutterspeed
        and ISO for taking photos of the desired brightness.
        """
        killtoken=False
        targetBrightness=self.project.brightness
        while abs(targetBrightness-self.lastbr)>4:
            options='-awb off -n'
            options+=' -w 64 -h 48'
            options+=' -t 10'
            options+=' -ss '+str(self.currentss)
            options+=' -ISO '+str(self.currentiso)
            options+=' -o new.jpg'
            subprocess.call('raspistill '+options, shell=True)
            im=Image.open('new.jpg')
            self.lastbr=self.avgbrightness(im)
            self.avgbr=self.lastbr

            #Dynamically adjust ss and iso.
            self.dynamic_adjust()
            print self.currentss, self.currentiso, self.lastbr
            if self.currentss==self.maxss and self.currentiso==self.maxiso: 
                if killtoken==True:
                    break
                else:
                    killtoken=True
            elif self.currentss==self.minss and self.currentiso==self.miniso:
                if killtoken==True:
                    break
                else:
                    killtoken=True
        return True
