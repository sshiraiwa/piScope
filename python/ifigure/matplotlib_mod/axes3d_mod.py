from matplotlib.image import FigureImage
from functools import wraps
from ifigure.matplotlib_mod.is_supported_renderer import isSupportedRenderer
from matplotlib.collections import Collection, LineCollection, \
    PolyCollection, PatchCollection, PathCollection
import numpy as np
from matplotlib.artist import allow_rasterization
import weakref
import ifigure.events as events
from scipy.signal import convolve2d, fftconvolve
from scipy.sparse import coo_matrix

from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.text import Text
from mpl_toolkits.mplot3d.axes3d import Axes3D
import mpl_toolkits.mplot3d.art3d as art3d
import matplotlib.transforms as trans
from matplotlib.colors import ColorConverter
from functools import reduce
cc = ColorConverter()


# KERNEL for mask bluring
conv_kernel_size = 11
x = 1-np.abs(np.linspace(-1., 1., conv_kernel_size))
X, Y = np.meshgrid(x, x)
conv_kernel = np.sqrt(X**2, Y**2)
conv_kernel = conv_kernel/np.sum(conv_kernel)
###


def convert_to_gl(obj, zs=0, zdir='z'):
    from art3d_gl import polygon_2d_to_gl
    from art3d_gl import line_3d_to_gl
    from art3d_gl import poly_collection_3d_to_gl
    from art3d_gl import line_collection_3d_to_gl
    from matplotlib.patches import Polygon
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3D, \
        poly_collection_2d_to_3d, Line3DCollection

    if isinstance(obj, Line3D):
        line3d_to_gl(obj)
    elif isinstance(obj, Polygon):
        polygon_2d_to_gl(obj, zs, zdir)
    elif isinstance(obj, Poly3DCollection):
        poly_collection_3d_to_gl(obj)
    elif isinstance(obj, Line3DCollection):
        line_collection_3d_to_gl(obj)
    elif isinstance(obj, PolyCollection):
        poly_collection_2d_to_3d(obj, zs=zs, zdir=zdir)
        poly_collection_3d_to_gl(obj)


def get_glcanvas():
    from ifigure.matplotlib_mod.backend_wxagg_gl import FigureCanvasWxAggModGL
    return FigureCanvasWxAggModGL.glcanvas


def norm_vec(n):
    d = np.sum(n**2)
    if d == 0:
        return [0, 0, 0]
    else:
        return n/np.sqrt(d)


def arrow3d(base, r1, r2, ort, l, h, m=13, pivot='tail'):
    x = np.array([1., 0., 0.])
    y = np.array([0., 1., 0.])
    th = np.linspace(0, np.pi*2, m).reshape(-1, 1)
    ort = norm_vec(ort)
    if np.sum(ort * x) == 0:
        d1 = norm_vec(np.cross(ort, y))
    else:
        d1 = norm_vec(np.cross(ort, x))
    if pivot == 'tip':
        base = base - (l+h)*ort
    elif pivot == 'mid':
        base = base - (l+h)*ort/2.
    else:
        pass
    d2 = np.cross(ort, d1)
    p = base + l*r1 * (d1*np.cos(th) + d2*np.sin(th))
    q = p + l*ort
    p2 = base + l*r2 * (d1*np.cos(th) + d2*np.sin(th)) + l*ort
    p3 = base + (l+h)*ort
    p3 = np.array([p3]*m).reshape(-1, 3)
    t1 = np.stack((p[:-1], q[:-1], p[1:]), axis=1)
    t2 = np.stack((p[1:], q[:-1], q[1:]), axis=1)
    t3 = np.stack((p2[:-1], p3[:-1], p2[1:]), axis=1)
    #t2 = np.dstack((p[1:], q[:-1], q[1:]))
    t1 = np.vstack((t1, t2, t3))
    return t1


def world_transformation(xmin, xmax,
                         ymin, ymax,
                         zmin, zmax,
                         view_scale=1):
    dx, dy, dz = (xmax-xmin), (ymax-ymin), (zmax-zmin)
    return np.array([
        [1.0/dx, 0, 0, -xmin/dx],
        [0, 1.0/dy, 0, -ymin/dy],
        [0, 0, 1.0/dz, -zmin/dz],
        [0, 0, 0, 1.0]])


def view_transformation(E, R, V):
    n = (E - R)
    # new
#    n /= mod(n)
#    u = np.cross(V,n)
#    u /= mod(u)
#    v = np.cross(n,u)
#    Mr = np.diag([1.]*4)
#    Mt = np.diag([1.]*4)
#    Mr[:3,:3] = u,v,n
#    Mt[:3,-1] = -E
    # end new

    # old
    n = n / np.sqrt(np.sum(n**2))
    u = np.cross(V, n)
    u = u / np.sqrt(np.sum(u**2))
    v = np.cross(n, u)
    Mr = [[u[0], u[1], u[2], 0],
          [v[0], v[1], v[2], 0],
          [n[0], n[1], n[2], 0],
          [0,   0,   0,   1],
          ]
    #
    Mt = [[1, 0, 0, -E[0]],
          [0, 1, 0, -E[1]],
          [0, 0, 1, -E[2]],
          [0, 0, 0, 1]]
    # end old

    return np.dot(Mr, Mt)


def persp_transformation(zfront, zback):
    a = (zfront+zback)/(zfront-zback)
    b = -2*(zfront*zback)/(zfront-zback)
    from ifigure.matplotlib_mod.canvas_common import view_scale
    return np.array([[view_scale, 0, 0, 0],
                     [0, view_scale, 0, 0],
                     [0, 0, a, b],
                     [0, 0, -1, 0]
                     ])


def use_gl_switch(func):
    '''
    use_gl_switch allows to select types of 3D plot
    aritist, either mplot3d or openGL based artist.

    note that piScope does not keep track
    use_gl switch. Manipulating use_gl manually in 
    piScope makes your plot unreproducible.
    '''
    @wraps(func)
    def checker(self, *args, **kargs):
        if self._use_gl:
            m = func
            ret = m(self, *args, **kargs)
        else:
            m = getattr(super(Axes3DMod, self), func.__name__)
            ret = m(*args, **kargs)
        return ret
    return checker


class ArtGLHighlight(FigureImage):
    def remove(self):
        self.figure.artists.remove(self)


class Axes3DMod(Axes3D):
    pan_sensitivity = 5

    def __init__(self, *args, **kargs):
        self._nomargin_mode = False
        self._offset_trans_changed = False
        self._mouse_hit = False
        self._lighting = {'light': 0.5,
                          'ambient': 0.5,
                          'specular': .0,
                          'light_direction': (1., 0, 1, 0),
                          'light_color': (1., 1., 1),
                          'wireframe': 0,
                          'clip_limit1': [0., 0., 0.],
                          'clip_limit2': [1., 1., 1.],
                          'shadowmap': False}
        self._use_gl = kargs.pop('use_gl', True)
        self._use_frustum = kargs.pop('use_frustum', True)
        self._use_clip = kargs.pop('use_clip', True)
        super(Axes3DMod, self).__init__(*args, **kargs)
        self.patch.set_alpha(0)
        self._gl_id_data = None
        self._gl_mask_artist = None
        self._3d_axes_icon = None
        self._show_3d_axes = True
        self._upvec = np.array([0, 0, 1])
        self._ignore_screen_aspect_ratio = True
        self._gl_scale = 1.0

    def view_init(self, elev=None, azim=None):
        """
        Copied form Axes3D to play with self.dist
        """
        from ifigure.matplotlib_mod.canvas_common import camera_distance
        self.dist = camera_distance  # default 10

        if elev is None:
            self.elev = self.initial_elev
        else:
            self.elev = elev

        if azim is None:
            self.azim = self.initial_azim
        else:
            self.azim = azim

    def gl_hit_test(self, x, y, artist, radius=3):
        #
        #  logic is
        #     if artist_id is found within raidus from (x, y)
        #     and
        #     if it is the closet artist in the area of checking
        #     then return True
        if self._gl_id_data is None:
            return False, None

        x0, y0, id_dict, im, imd, im2 = self._gl_id_data
        x, x0,  y, y0 = int(x), int(x0),  int(y), int(y0)
        d = np.rint((im[y-y0-radius:y-y0+radius,
                        x-x0-radius:x-x0+radius]).flatten())
        '''
        print(im2[y-y0-radius:y-y0+radius,
                  x-x0-radius:x-x0+radius])
        print(imd[y-y0-radius:y-y0+radius,
                  x-x0-radius:x-x0+radius])
        '''
        dd = (im2[y-y0-radius:y-y0+radius,
                  x-x0-radius:x-x0+radius]).flatten()
        dd_extra = (imd[y-y0-radius:y-y0+radius,
                        x-x0-radius:x-x0+radius]).flatten()
        if len(dd) == 0:
            return False, None

        mask = np.array([id_dict[x]()._gl_pickable if x in id_dict
                         and id_dict[x]() is not None else False
                         for x in d])
        if not any(mask):
            return False, None

        dist = np.min(dd[mask])

        for num, check, check2 in zip(d, dd, dd_extra):
            if num in id_dict:
                if id_dict[num]() == artist and check == dist:
                    return True, check2

        return False, None

    def make_gl_hl_artist(self):
        if self._gl_id_data is None:
            return []
        self.del_gl_hl_artist()

        x0, y0, id_dict, im, imd, im2 = self._gl_id_data
        a = ArtGLHighlight(self.figure, offsetx=x0,
                           offsety=y0, origin='lower')
        data = np.ones(im.shape)
        alpha = np.zeros(im.shape)
        mask = np.dstack((data, data, data, alpha))
        a.set_array(mask)
        self.figure.artists.append(a)
        self._gl_mask_artist = a

        return [a]

    def del_gl_hl_artist(self):
        if self._gl_mask_artist is not None:
            self._gl_mask_artist.remove()
        self._gl_mask_artist = None

    def set_gl_hl_mask(self, artist, hit_id=None,
                       cmask=0.0, amask=0.65):
        #
        #  logic is
        #     if artist_id is found within raidus from (x, y)
        #     and
        #     if it is the closet artist in the area of checking
        #     then return True

        if self._gl_id_data is None:
            return False
        if self._gl_mask_artist is None:
            return False

        # do not do this when hitest_map is updating..this is when
        # mouse dragging is going on
        if not get_glcanvas()._hittest_map_update:
            return
        x0, y0, id_dict, im, imd, im2 = self._gl_id_data

        arr = self._gl_mask_artist.get_array()

        for k in list(id_dict.keys()):
            if (id_dict[k]() == artist):
                if hit_id is not None:
                    if len(hit_id) > 0:
                        mask = np.isin(imd, hit_id)
                        m = np.logical_and(im == k, mask)
                    else:
                        m = (im == k)
                else:
                    m = (im == k)

                c = self.figure.canvas.hl_color
                arr[:, :, :3][m] = np.array(c, copy=False)
                arr[:, :, 3][m] = amask
                break
        # blur the mask,,,

    def blur_gl_hl_mask(self, amask=0.65):
        if self._gl_mask_artist is None:
            return
        arr = self._gl_mask_artist.get_array()
        #b = convolve2d(arr[:,:,3], conv_kernel, mode = 'same') + arr[:,:,3]
        b = fftconvolve(arr[:, :, 3], conv_kernel, mode='same') + arr[:, :, 3]
        #b = np.sqrt(b)
        b[b > amask] = amask

        c = self.figure.canvas.hl_color
        arr[b > 0.0, :3] = c
        arr[..., -1] = b
        self._gl_mask_artist.set_array(arr)

    def set_nomargin_mode(self, mode):
        self._nomargin_mode = mode

    def get_nomargin_mode(self):
        return self._nomargin_mode

    def get_zaxis(self):
        return self.zaxis

    #
    #   prepend and append some work to visual
    #   effect for 3D rotation
    #
    def set_mouse_button(self, rotate_btn=1, zoom_btn=3, pan_btn=2):
        self._pan_btn = np.atleast_1d(pan_btn)
        self._rotate_btn = np.atleast_1d(rotate_btn)
        self._zoom_btn = np.atleast_1d(zoom_btn)

#    def mouse_init(self, rotate_btn=1, zoom_btn=3, pan_btn=2):
#        self.set_mouse_button(rotate_btn=rotate_btn,
#                              zoom_btn=zoom_btn,
#                              pan_btn=pan_btn)
#        self._pan_btn = np.atleast_1d(pan_btn)
#        self._rotate_btn = np.atleast_1d(rotate_btn)
#        self._zoom_btn = np.atleast_1d(zoom_btn)
#        Axes3D.mouse_init(self, rotate_btn=rotate_btn, zoom_btn=zoom_btn)

    def _button_press(self, evt):
        self._mouse_hit, extra = self.contains(evt)
        if not self._mouse_hit:
            return
        fig_axes = self.figobj
#        for obj in fig_axes.walk_tree():
#            obj.switch_scale('coarse')
        Axes3D._button_press(self, evt)

    def _on_move(self, evt):
        if not self._mouse_hit:
            return
        fig_axes = self.figobj
        fig_axes.set_bmp_update(False)
        #Axes3D._on_move(self, evt)
        self._on_move_mod(evt)
        get_glcanvas()._hittest_map_update = False
        events.SendPVDrawRequest(self.figobj,
                                 w=None, wait_idle=False,
                                 refresh_hl=False,
                                 caller='_on_move')

    def _on_move_done(self):
        get_glcanvas()._hittest_map_update = True

    def calc_range_change_by_pan(self, xdata, ydata, sxdata, sydata):
        from ifigure.utils.geom import transform_point

        x0, y0 = transform_point(
            self.transAxes, 0.5, 0.5)
        x0, y0 = transform_point(
            self.transData.inverted(), x0, y0)

        dx = x0 - (xdata + sxdata)/2.0
        dy = y0 - (ydata + sydata)/2.0

        w = self._pseudo_w
        h = self._pseudo_h

        dx = dx/w
        dy = dy/h
        df = max(abs(xdata - sxdata)/w, abs(ydata - sydata)/h)

        minx, maxx, miny, maxy, minz, maxz = self.get_w_lims()

        midx = (minx+maxx)/2.
        midy = (miny+maxy)/2.
        midz = (minz+maxz)/2.
        M = self.get_proj()
        dp = -np.array([dx, dy])

        xx = (np.dot(M, (1, midy, midz, 1)) -
              np.dot(M, (0, midy, midz, 1)))[:2]
        dx1 = np.sum(xx * dp)/np.sum(xx *
                                     xx) if np.sum(xx * xx) > 0.01 else 0.0
        yy = (np.dot(M, (midx, 1, midz, 1)) -
              np.dot(M, (midx, 0, midz, 1)))[:2]
        dy1 = np.sum(yy * dp)/np.sum(yy *
                                     yy) if np.sum(yy * yy) > 0.01 else 0.0
        zz = (np.dot(M, (midx, midy, 1, 1)) -
              np.dot(M, (midx, midy, 0, 1)))[:2]
        dz1 = np.sum(zz * dp)/np.sum(zz *
                                     zz) if np.sum(zz * zz) > 0.01 else 0.0

        minx, maxx = minx + dx1, maxx + dx1
        miny, maxy = miny + dy1, maxy + dy1
        minz, maxz = minz + dz1, maxz + dz1

        dx = (maxx-minx)*df/2.
        dy = (maxy-miny)*df/2.
        dz = (maxz-minz)*df/2.
        x0 = (maxx+minx)/2.0
        y0 = (maxy+miny)/2.0
        z0 = (maxz+minz)/2.0

        return ((x0 - dx, x0 + dx), (y0 - dy, y0 + dy), (z0 - dz, z0 + dz))

    def _on_move_mod(self, event):
        """
        added pan mode 
        """

        if not self.button_pressed:
            return

        if self.M is None:
            return

        x, y = event.xdata, event.ydata
        # In case the mouse is out of bounds.
        if x is None:
            return

        dx, dy = x - self.sx, y - self.sy
        w = self._pseudo_w
        h = self._pseudo_h
        self.sx, self.sy = x, y

        # Rotation
        if self.button_pressed in self._rotate_btn:
            # rotate viewing point
            # get the x and y pixel coords
            if dx == 0 and dy == 0:
                return
            relev, razim = np.pi * self.elev/180, np.pi * self.azim/180
            p1 = np.array((np.cos(razim) * np.cos(relev),
                           np.sin(razim) * np.cos(relev),
                           np.sin(relev)))
            rightvec = np.cross(self._upvec, p1)
            #dx = dx/np.sqrt(dx**2 + dy**2)/3.
            #dy = dy/np.sqrt(dx**2 + dy**2)/3.
            newp1 = p1 - (dx/w*rightvec + dy/h*self._upvec) * \
                Axes3DMod.pan_sensitivity
            newp1 = newp1/np.sqrt(np.sum(newp1**2))
            self._upvec = self._upvec - newp1*np.sum(newp1*self._upvec)
            self._upvec = self._upvec/np.sqrt(np.sum(self._upvec**2))
            self.elev = np.arctan2(newp1[2], np.sqrt(
                newp1[0]**2+newp1[1]**2))*180/np.pi
            self.azim = np.arctan2(newp1[1], newp1[0])*180/np.pi
#            self.elev = art3d.norm_angle(self.elev - (dy/h)*180)
#            self.azim = art3d.norm_angle(self.azim - (dx/w)*180)
            # self.get_proj()
            # self.figure.canvas.draw_idle()

        elif self.button_pressed in self._pan_btn:
            dx = 1-((w - dx)/w)
            dy = 1-((h - dy)/h)
            relev, razim = np.pi * self.elev/180, np.pi * self.azim/180
            p1 = np.array((np.cos(razim) * np.cos(relev),
                           np.sin(razim) * np.cos(relev),
                           np.sin(relev)))
            rightvec = np.cross(self._upvec, p1)  # right on screen

            #p2 = np.array((np.sin(razim), -np.cos(razim), 0))
            #p3 = np.cross(p1, p2)
            #dx, dy, dz = p2*dx + p3*dy
            dx, dy, dz = -rightvec * dx - self._upvec * dy
            minx, maxx, miny, maxy, minz, maxz = self.get_w_lims()
            dx = (maxx-minx)*dx
            dy = (maxy-miny)*dy
            dz = (maxz-minz)*dz

            self.set_xlim3d(minx + dx, maxx + dx)
            self.set_ylim3d(miny + dy, maxy + dy)
            self.set_zlim3d(minz + dz, maxz + dz)

            # self.get_proj()
            # self.figure.canvas.draw_idle()

            # pan view
            # project xv,yv,zv -> xw,yw,zw
            # pan

        # Zoom
        elif self.button_pressed in self._zoom_btn:
            # zoom view
            # hmmm..this needs some help from clipping....
            minx, maxx, miny, maxy, minz, maxz = self.get_w_lims()
            df = 1-((h - dy)/h)
            dx = (maxx-minx)*df
            dy = (maxy-miny)*df
            dz = (maxz-minz)*df
            self.set_xlim3d(minx - dx, maxx + dx)
            self.set_ylim3d(miny - dy, maxy + dy)
            self.set_zlim3d(minz - dz, maxz + dz)
            # self.get_proj()
            # self.figure.canvas.draw_idle()

    def _button_release(self, evt):
        if not self._mouse_hit:
            return

        fig_axes = self.figobj
        fig_axes.set_bmp_update(False)
        Axes3D._button_release(self, evt)
        # events.SendPVDrawRequest(self.figobj,
        #                         w=None, wait_idle=False,
        #                         refresh_hl=False,
        #                         caller = '_on_release')

    @use_gl_switch
    def plot(self, *args, **kwargs):
        from art3d_gl import line_3d_to_gl
        fc = kwargs.pop('facecolor', None)
        gl_offset = kwargs.pop('gl_offset', (0, 0, 0))
        array_idx = kwargs.pop('array_idx', None)
        lines = Axes3D.plot(self, *args, **kwargs)
        for l in lines:
            line_3d_to_gl(l)
            l._facecolor = fc
            l._gl_offset = gl_offset
            l._gl_array_idx = array_idx
        return lines

    def fill(self, *args, **kwargs):
        from art3d_gl import polygon_2d_to_gl
        zs = kwargs.pop('zs', 0)
        zdir = kwargs.pop('zdir', 'z')
        a = Axes3D.fill(self, *args, **kwargs)

        for obj in a:
            convert_to_gl(obj, zs, zdir)
        return a

    def fill_between(self, *args, **kwargs):
        from art3d_gl import polygon_2d_to_gl
        zs = kwargs.pop('zs', 0)
        zdir = kwargs.pop('zdir', 'z')
        a = Axes3D.fill_between(self, *args, **kwargs)
        convert_to_gl(a, zs, zdir)
        a.convert_2dpath_to_3dpath(zs, zdir=zdir)
        return a

    def fill_betweenx(self, *args, **kwargs):
        from art3d_gl import polygon_2d_to_gl
        zs = kwargs.pop('zs', 0)
        zdir = kwargs.pop('zdir', 'z')
        a = Axes3D.fill_betweenx(self, *args, **kwargs)
        convert_to_gl(a, zs, zdir)
        a.convert_2dpath_to_3dpath(zs, zdir=zdir)
        return a

    def cz_plot(self, x, y, z, c, **kywds):
        from ifigure.matplotlib_mod.art3d_gl import Line3DCollectionGL
        a = Line3DCollectionGL([], c_data=c, gl_lighting=False,  **kywds)
        a._segments3d = (np.transpose(
            np.vstack((np.array(x), np.array(y), np.array(z)))),)
        a.convert_2dpath_to_3dpath()
        a.set_alpha(1.0)
        self.add_collection(a)
        return a

    def contour(self, *args, **kwargs):
        from art3d_gl import poly_collection_3d_to_gl
        offset = kwargs['offset'] if 'offset' in kwargs else None
        zdir = kwargs['zdir'] if 'zdir' in kwargs else 'z'
        cset = Axes3D.contour(self, *args, **kwargs)
        for z, linec in zip(np.argsort(cset.levels), cset.collections):
            convert_to_gl(linec)
            linec.convert_2dpath_to_3dpath(z, zdir='z')
            linec.do_stencil_test = True
            if offset is not None:
                if zdir == 'x':
                    linec._gl_offset = (z*0.001, 0, 0)
                elif zdir == 'y':
                    linec._gl_offset = (0, z*0.001, 0)
                else:
                    linec._gl_offset = (0, 0, z*0.001)
        return cset

    def imshow(self, *args, **kwargs):
        im_center = kwargs.pop('im_center', (0, 0))
        im_axes = kwargs.pop('im_axes', [(1, 0, 0), (0, 1, 0)])

        from art3d_gl import image_to_gl
        im = Axes3D.imshow(self, *args, **kwargs)
        image_to_gl(im)
        im.set_3dpath(im_center, im_axes)
        return im

    def contourf(self, *args, **kwargs):
        from art3d_gl import poly_collection_3d_to_gl
        offset = kwargs['offset'] if 'offset' in kwargs else None
        zdir = kwargs['zdir'] if 'zdir' in kwargs else 'z'
        cset = Axes3D.contourf(self, *args, **kwargs)
        edgecolor = kwargs.pop('edgecolor', [1, 1, 1, 0])
        for z, linec in zip(np.argsort(cset.levels), cset.collections):
            convert_to_gl(linec)
            linec.convert_2dpath_to_3dpath(z, zdir='z')
            linec.do_stencil_test = True
            if offset is not None:
                if zdir == 'x':
                    linec._gl_offset = (z*0.001, 0, 0)
                elif zdir == 'y':
                    linec._gl_offset = (0, z*0.001, 0)
                else:
                    linec._gl_offset = (0, 0, z*0.001)
            linec.set_edgecolor((edgecolor,))
        return cset

    def quiver(self, *args, **kwargs):
        '''
         quiver(x, y, z, u, v, w, length=0.1, normalize = True, **kwargs)  

            kwargs: facecolor
                    edgecolor
                    alpha
                    cz, cdata

        '''
        # made based on mplot3d but makes GL solid object
        # handle kwargs
        # shaft length
        length = kwargs.pop('length', 1.0)
        # arrow length ratio to the shaft length
        arrow_length_ratio = kwargs.pop('arrow_length_ratio', 0.3)
        # pivot point (not implemeted)
        pivot = kwargs.pop('pivot', 'tail')
        # normalize
        normalize = kwargs.pop('normalize', False)

        # handle args
        argi = 6
        if len(args) < argi:
            ValueError('Wrong number of arguments. Expected %d got %d' %
                       (argi, len(args)))

        # first 6 arguments are X, Y, Z, U, V, W
        input_args = args[:argi]
        # if any of the args are scalar, convert into list
        input_args = [[k] if isinstance(k, (int, float)) else k
                      for k in input_args]

        # extract the masks, if any
        masks = [k.mask for k in input_args if isinstance(
            k, np.ma.MaskedArray)]
        # broadcast to match the shape
        bcast = np.broadcast_arrays(*(input_args + masks))
        input_args = bcast[:argi]
        masks = bcast[argi:]
        if masks:
            # combine the masks into one
            mask = reduce(np.logical_or, masks)
            # put mask on and compress
            input_args = [np.ma.array(k, mask=mask).compressed()
                          for k in input_args]
        else:
            input_args = [k.flatten() for k in input_args]
        XYZ = np.column_stack(input_args[:3])
        UVW = np.column_stack(input_args[3:argi]).astype(float)

        norm = np.sqrt(np.sum(UVW**2, axis=1))
        # If any row of UVW is all zeros, don't make a quiver for it
        mask = norm > 0
        norm = norm[mask]
        XYZ = XYZ[mask]
        ORT = UVW[mask] / norm.reshape((-1, 1))
        if normalize:
            norm = np.array([length]*len(ORT))
        else:
            norm = norm/np.max(norm)*length

        h = np.max(norm)*arrow_length_ratio
        r1 = kwargs.pop('shaftsize', 0.05)
        r2 = kwargs.pop('headsize', 0.25)

        m = 13
        sample_len = len(
            arrow3d(XYZ[0], r1, r2, ORT[0], norm[0], h, m=m, pivot=pivot))
        v = np.vstack([arrow3d(base, r1, r2, ort, l, h, m=m, pivot=pivot)
                       for base, ort, l in zip(XYZ, ORT, norm)],)
        cdata = kwargs.pop('facecolordata', None)
        if cdata is not None:
            cdata = np.transpose(
                np.vstack([cdata.flatten()]*sample_len)).flatten()
            kwargs['facecolordata'] = cdata

        return self.plot_solid(v, **kwargs)

    def plot_revolve(self, R, Z,  *args, **kwargs):
        '''
        revolve

        '''
        raxis = np.array(kwargs.pop('raxis', (0,  1)))
        rtheta = kwargs.pop('rtheta', (0, np.pi*2))
        rmesh = kwargs.pop('rmesh', 30)
        rcenter = np.array(kwargs.pop('rcenter', [0, 0]))
        theta = np.linspace(rtheta[0], rtheta[1], rmesh)

        pos = np.vstack((R-rcenter[0], Z-rcenter[1]))
        nraxis = raxis/np.sqrt(np.sum(raxis**2))
        nraxis = np.hstack([nraxis.reshape(2, -1)]*len(R))
        nc = np.hstack([rcenter.reshape(2, -1)]*len(R))
        dcos = np.sum(pos*nraxis, 0)
        newz = nc + dcos  # center of rotation
        dsin = pos[0, :]*nraxis[1, :] - pos[1, :]*nraxis[0, :]

#        Theta, R = np.meshgrid(theta, np.abs(dsin))
#        void, Z = np.meshgrid(theta, dcos)
        R, Theta = np.meshgrid(np.abs(dsin), theta)
        Z, void = np.meshgrid(dcos, theta)

        X = R*np.cos(Theta)
        Y = R*np.sin(Theta)

        tt = np.pi/2-np.arctan2(raxis[1], raxis[0])
        m = np.array([[np.cos(tt), 0, -np.sin(tt)],
                      [0, 1, 0],
                      [np.sin(tt), 0, np.cos(tt)], ])

        dd = np.dot(np.dstack((X, Y, Z)), m)
        X = dd[:, :, 0]+rcenter[0]
        Y = dd[:, :, 1]
        Z = dd[:, :, 2] + rcenter[1]

#        from ifigure.interactive import figure
#        v = figure()
#        v.plot(X, Z)
        #facecolor = kwargs.pop('facecolor', (0,0,1,1))
        X, Y, Z = np.broadcast_arrays(X, Y, Z)
        polyc = self.plot_surface(X, Y, Z, *args, **kwargs)
        polyc._revolve_data = (X, Y, Z)
        return polyc

    def plot_extrude(self, X, Y, Z, path,
                     scale=None, revolve=False):
        '''
        extrude a path drawn by X, Y, Z along the path
            path.shape = [:, 3]

         A, B = np.meshgrid(ai, bj)
           A.shape = (j, i). A[j,i] = ai
           B.shape = (j, i). B[j,i] = bj

           X[j, i] = X[i] - path_x[0] + path_x[j]
           X.flatten() = X[0, :], X[1,:], X[2,:]
        '''
        facecolor = kwargs.pop('facecolor', (0, 0, 1, 1))
        scale = kwargs.pop('scale', 1.0)
        scale = kwargs.pop('scale', 1.0)
        x1, x2 = np.meshgrid(path[:, 0], X)
        x = x1 + x2 - path[0, 0]
        y1, y2 = np.meshgrid(path[:, 1], Y)
        y = y1 + y2 - path[0, 1]
        z1, z2 = np.meshgrid(path[:, 2], Z)
        z = z1 + z2 - path[0, 2]

        X = x.flatten()
        Y = y.flatten()
        Z = z.flatten()
        polyc = self.plot_surface(X, Y, Z, *args, **kwargs)
        return polyc

    def plot_surface(self, X, Y, Z, *args, **kwargs):
        '''
        Create a surface plot using OpenGL-based artist

        By default it will be colored in shades of a solid color,
        but it also supports color mapping by supplying the *cmap*
        argument.

        ============= ================================================
        Argument      Description
        ============= ================================================
        *X*, *Y*, *Z* Data values as 2D arrays
        *edgecolor*   Color of the surface patches (default 'k')
        *facecolor*   Color of the surface patches (default None: use cmap)
        *rstride*     Reduce data 
        *cstride*     Reduce data 
        *cmap*        A colormap for the surface patches.
        *shade*       Whether to shade the facecolors
        ============= ================================================

        Other arguments are passed on to
        :class:`~mpl_toolkits.mplot3d.art3d.Poly3DCollection`
        '''
        cz = kwargs.pop('cz', False)
        cdata = kwargs.pop('cdata', None)
        expanddata = kwargs.pop('expanddata', False)

        Z = np.atleast_2d(Z)
        # TODO: Support masked arrays
        if Y.ndim == 1 and X.ndim == 1:
            X, Y = np.meshgrid(X, Y)
        X, Y, Z = np.broadcast_arrays(X, Y, Z)
        rows, cols = Z.shape

        rstride = kwargs.pop('rstride', 10)
        cstride = kwargs.pop('cstride', 10)
        idxset3d = []
        r = list(range(0, rows, rstride))
        c = list(range(0, cols, cstride))

        X3D = X[r, :][:, c].flatten()
        Y3D = Y[r, :][:, c].flatten()
        Z3D = Z[r, :][:, c].flatten()

        # array index
        idxset = []
        l_r = len(r)
        l_c = len(c)
#        offset = np.array([0, 1, l_c+1, l_c, 0])
        offset = np.array([0, 1, l_c+1, l_c])
        base = np.arange(l_r*l_c).reshape(l_r, l_c)
        base = base[:-1, :-1].flatten()

        idxset = np.array([x + offset for x in base], 'H')

        if expanddata:
            verts = np.dstack((X3D[idxset],
                               Y3D[idxset],
                               Z3D[idxset]))
            if cz:
                if cdata is not None:
                    cdata = cdata[r, :][:, c].flatten()[idxset]
                else:
                    cdata = Z3D[idxset]
                shade = kwargs.pop('shade', 'flat')
                if shade != 'linear':
                    cdata = np.mean(cdata, -1)
                kwargs['facecolordata'] = np.real(cdata)
                kwargs.pop('facecolor', None)  # get rid of this keyword
            kwargs['cz'] = cz
            o = self.plot_solid(verts, **kwargs)
            o._idxset = (r, c, idxset)   # this is used for phasor
        else:
            verts = np.vstack((X3D, Y3D, Z3D)).transpose()
            if cz:
                if cdata is not None:
                    cdata = cdata[r, :][:, c].flatten()
                else:
                    cdata = Z3D
                shade = kwargs.get('shade', 'flat')
                kwargs['facecolordata'] = np.real(cdata)
                kwargs.pop('facecolor', None)  # get rid of this keyword
            kwargs['cz'] = cz
            o = self.plot_solid(verts, idxset, **kwargs)
            o._idxset = (r, c, None)   # this is used for phasor
        return o

    def plot_trisurf(self, *args, **kwargs):
        '''
        plot_trisurf(x, y, z,  **wrargs)
        plot_trisurf(x, y, z,  triangles = triangle,,,)
        plot_trisurf(tri, z,  **kwargs, cz = cz, cdata = cdata)


        '''
        from art3d_gl import poly_collection_3d_to_gl
        from matplotlib.tri.triangulation import Triangulation

        cz = kwargs.pop('cz', False)
        cdata = kwargs.pop('cdata', None)
        expanddata = kwargs.pop('expanddata', False)

        tri, args, kwargs = Triangulation.get_from_args_and_kwargs(
            *args, **kwargs)
        if 'Z' in kwargs:
            z = np.asarray(kwargs.pop('Z'))
        else:
            z = np.asarray(args[0])
            # We do this so Z doesn't get passed as an arg to PolyCollection
            args = args[1:]

        triangles = tri.get_masked_triangles()
        X3D = tri.x
        Y3D = tri.y
        Z3D = z
        idxset = tri.get_masked_triangles()

        if expanddata:
            verts = np.dstack((X3D[idxset],
                               Y3D[idxset],
                               Z3D[idxset]))
            if cz:
                if cdata is not None:
                    cdata = cdata[idxset]
                else:
                    cdata = Z3D[idxset]
                shade = kwargs.pop('shade', 'linear')
                if shade != 'linear':
                    cdata = np.mean(cdata, -1)
                kwargs['facecolordata'] = np.real(cdata)
                kwargs.pop('facecolor', None)  # get rid of this keyword
            kwargs['cz'] = cz
            o = self.plot_solid(verts, **kwargs)
            o._idxset = (None, None, idxset)   # this is used for phasor
        else:
            verts = np.vstack((X3D, Y3D, Z3D)).transpose()
            if cz:
                if cdata is not None:
                    cdata = cdata
                else:
                    cdata = Z3D
                kwargs['facecolordata'] = np.real(cdata)
                kwargs.pop('facecolor', None)  # get rid of this keyword
            kwargs['cz'] = cz
            o = self.plot_solid(verts, idxset, **kwargs)
            o._idxset = (None, None, None)   # this is used for phasor
        return o

    def prep_flat_shading_data(self, args, kwargs):
        if len(args) < 2:
            return args, kwargs

        vert = args[0]
        idx = args[1]
        args = (vert[idx],)
        if 'array_idx' in kwargs:
            if kwargs['array_idx'] is not None:
                kwargs['array_idx'] = kwargs['array_idx'][idx].flatten()
        if 'facecolordata' in kwargs:
            cdata = kwargs['facecolordata'][idx]
            cdata = np.mean(cdata, 1)
            kwargs['facecolordata'] = cdata
        return args, kwargs

    def plot_solid(self, *args,  **kwargs):
        '''
        plot_solid(v)  or plot_solid(v, idx)

        v [element_index, points_in_element, xyz]

        or 

        v [vertex_index, xyz]
        idx = [element_idx, point_in_element]

        kwargs: normals : normal vectors
        '''
        shade = kwargs.pop('shade', 'linear')
        if shade == 'flat':
            args, kwargs = self.prep_flat_shading_data(args, kwargs)

        if len(args) == 1:
            v = args[0]
            vv = v.reshape(-1, v.shape[-1])  # vertex
            nv = len(v[:, :, 2].flatten())
            idxset = np.arange(nv, dtype=int).reshape(v.shape[0], v.shape[1])
            nverts = v.shape[0]*v.shape[1]
            ncounts = v.shape[1]
            nele = v.shape[0]
        else:
            v = args[0]   # vertex
            vv = v
            idxset = np.array(args[1], dtype=int, copy=False)
            # element index (element_idx, point_in_element)
            nverts = v.shape[0]
            ncounts = idxset.shape[1]
            nele = idxset.shape[0]

        norms = kwargs.pop('normals', None)

        w = np.zeros((nverts))  # weight
        if norms is None:
            norms = np.zeros((nverts, 3), dtype=np.float32)  # weight
            if idxset.shape[1] > 2:
                xyz = vv[idxset[:, :3]].astype(float, copy=False)
                p0 = xyz[:, 0, :] - xyz[:, 1, :]
                p1 = xyz[:, 0, :] - xyz[:, 2, :]
                n1a = np.cross(p0, p1)
                da = np.sqrt(np.sum(n1a**2, 1))
                da[da == 0.0] = 1.
                n1a[:, 0] /= -da
                n1a[:, 1] /= -da
                n1a[:, 2] /= -da
            else:
                da = np.zeros(idxset.shape[0])
                n1a = np.zeros((nverts, 3), dtype=np.float32)  # weight
                n1a[:, 2] = 1.0

            if len(args) == 1:
                if da[0] == 0.:
                    norms[:, 2] = 1  # all [0. 0. 1]
                else:
                    for k in range(idxset.shape[1]):
                        norms[idxset[:, k], :] = n1a
            elif idxset.shape[-1] < 3:
                norms = n1a
            else:
                data = np.ones(idxset.flatten().shape[0])
                jj = np.tile(np.arange(idxset.shape[0]), idxset.shape[-1])
                ii = idxset.transpose().flatten()
                table = coo_matrix((data, (ii, jj)),
                                   shape=(nverts, idxset.shape[0]))
                csr = table.tocsr()
                indptr = csr.indptr
                indices = csr.indices

                data = csr.data
                for i in range(csr.shape[0]):
                    nn = n1a[indices[indptr[i]:indptr[i+1]]]
                    if len(nn) != 0.0:
                        sign = np.sign(np.sum(nn*nn[0], 1))
                        data[indices[indptr[i]:indptr[i+1]]] = sign
                    else:
                        pass
                        #norms[i, :] = [1,0,0]
                norms = table.dot(n1a)
                '''
                for i in range(csr.shape[0]):
                    nn = n1a[indices[indptr[i]:indptr[i+1]]]
                    if len(nn) != 0.0:
                       sign = np.sign(np.sum(nn*nn[0], 1))
                       nn *= np.tile(sign.reshape(sign.shape[0], 1), nn.shape[-1])
                       norms[i, :] = np.mean(nn, 0)
                    else:
                       norms[i, :] = [1,0,0]
                '''
                '''       
                table = table.tocsr()
                nz = n1a[:,2]
                nz[nz==0] = 1.0
                f = nz/np.abs(nz)
                n1a = (n1a.transpose()*f).transpose()
                norms = table.dot(n1a)
                '''
            nn = np.sqrt(np.sum(norms**2, 1))
            nn[nn == 0.0] = 1.
            norms = norms/nn.reshape(-1, 1)

        kwargs['gl_3dpath'] = [v[..., 0].flatten(),
                               v[..., 1].flatten(),
                               v[..., 2].flatten(),
                               norms,  idxset]

        from art3d_gl import Poly3DCollectionGL
        if len(args) == 1:
            a = Poly3DCollectionGL(v[:2, ...], **kwargs)
        else:
            a = Poly3DCollectionGL(v[idxset[:2, ...]], **kwargs)

        # For GL aritsts, it is not necesasry to put in collections??
        #Axes3D.add_collection3d(self, a)
        Axes3D.add_artist(self, a)
        a.do_stencil_test = False

        return a

    def get_proj2(self):
        '''
        based on mplot3d::get_proj()
        it exposes matries used to compose projection matrix,
        and supports orthogonal projection.
        '''
        relev, razim = np.pi * self.elev/180, np.pi * self.azim/180

        xmin, xmax = self.get_xlim3d()
        ymin, ymax = self.get_ylim3d()
        zmin, zmax = self.get_zlim3d()

        # transform to uniform world coordinates 0-1.0,0-1.0,0-1.0
        worldM = world_transformation(xmin, xmax, ymin, ymax, zmin, zmax,
                                      view_scale=self._gl_scale)

        # look into the middle of the new coordinates
        R = np.array([0.5, 0.5, 0.5])

        xp = R[0] + np.cos(razim) * np.cos(relev) * self.dist
        yp = R[1] + np.sin(razim) * np.cos(relev) * self.dist
        zp = R[2] + np.sin(relev) * self.dist
        E = np.array((xp, yp, zp))

        self.eye = E
        self.vvec = R - E
        self.vvec = self.vvec / np.sqrt(np.sum(self.vvec**2))

        if abs(relev) > np.pi/2:
            V = np.array((0, 0, -1))
        else:
            V = np.array((0, 0, 1))
        V = self._upvec
        zfront, zback = -self.dist, self.dist
        #zfront, zback = self.dist-1, self.dist+1

        viewM = view_transformation(E, R, V)
        if self._use_frustum:
            perspM = persp_transformation(zfront, zback)
        else:
            a = (zfront+zback)/(zfront-zback)
            b = -2*(zfront*zback)/(zfront-zback)
            perspM = np.array([[1, 0, 0, 0],
                               [0, 1, 0, 0],
                               [0, 0, a, b],
                               [0, 0, -1/10000., self.dist]
                               ])

        if self._ignore_screen_aspect_ratio:
            M = np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                          [0, 0, 1, 0], [0, 0, 0, 1]])
        else:
            bb = self.get_window_extent()
            r = abs((bb.x1-bb.x0)/(bb.y1-bb.y0))
            if r >= 1:
                M = np.array([[1./r, 0, 0, 0], [0, 1, 0, 0],
                              [0, 0, 1, 0], [0, 0, 0, 1]])
            else:
                M = np.array([[1, 0, 0, 0], [0, r, 0, 0],
                              [0, 0, 1, 0], [0, 0, 0, 1]])
        self._matrix_cache_extra = M

        perspM = np.dot(M, perspM)

        # perspM is used to draw Axes,,,
        return worldM, viewM, perspM, E, R, V, self.dist

    def get_proj(self):
        worldM, viewM, perspM, E, R, V, self.dist = self.get_proj2()
        M0 = np.dot(viewM, worldM)
        M = np.dot(perspM, M0)
        return M

    def set_lighting(self, *args, **kwargs):
        if len(args) != 0:
            kwargs = args[0]
        for k in kwargs:
            if k in self._lighting:
                self._lighting[k] = kwargs[k]

    def get_lighting(self):
        return self._lighting

    def show_3d_axes(self, value):
        self._show_3d_axes = value

    def draw_3d_axes(self):
        M = self.get_proj()
        dx = self.get_xlim()
        dy = self.get_ylim()
        dz = self.get_zlim()
        xvec = np.dot(M, np.array([abs(dx[1]-dx[0]), 0, 0, 0]))[:2]
        yvec = np.dot(M, np.array([0, abs(dy[1]-dy[0]), 0, 0]))[:2]
        zvec = np.dot(M, np.array([0, 0, abs(dz[1]-dz[0]), 0]))[:2]

        po = self.transAxes.transform([0.1, 0.1])
        pod = self.transData.transform([0.0, 0.0])
        fac = np.sqrt(np.sum((xvec-pod)**2 + (yvec-pod)**2 + (zvec-pod)**2))/5.

        tt = self.transData.inverted()

        def ptf(x):
            pp = self.transData.transform(x)
            st = tt.transform(po)
            et = tt.transform((pp-pod)/fac+po)
            et2 = tt.transform(1.5*(pp-pod)/fac+po)
            return [st[0], et[0]], [st[1], et[1]], et2

        if self._3d_axes_icon is None:
            p0, p1, pt = ptf(xvec)
            a1 = Line2D(p0, p1,
                        color='r', axes=self, figure=self.figure)
            a4 = Text(pt[0], pt[1], 'x', color='r',
                      axes=self, figure=self.figure,
                      transform=self.transData,
                      verticalalignment='center',
                      horizontalalignment='center')

            p0, p1, pt = ptf(yvec)
            a2 = Line2D(p0, p1,
                        color='g', axes=self, figure=self.figure)
            a5 = Text(pt[0], pt[1], 'y', color='g',
                      axes=self, figure=self.figure,
                      transform=self.transData,
                      verticalalignment='center',
                      horizontalalignment='center')

            p0, p1, pt = ptf(zvec)
            a3 = Line2D(p0, p1,
                        color='b', axes=self, figure=self.figure)
            a6 = Text(pt[0], pt[1], 'z', color='b',
                      axes=self, figure=self.figure,
                      transform=self.transData,
                      verticalalignment='center',
                      horizontalalignment='center')

            self.add_line(a1)
            self.add_line(a2)
            self.add_line(a3)
            self.texts.append(a4)
            self.texts.append(a5)
            self.texts.append(a6)
            self._3d_axes_icon = [weakref.ref(a1),
                                  weakref.ref(a2),
                                  weakref.ref(a3),
                                  weakref.ref(a4),
                                  weakref.ref(a5),
                                  weakref.ref(a6)]
        else:
            p0, p1, pt = ptf(xvec)
            self._3d_axes_icon[0]().set_xdata(p0)
            self._3d_axes_icon[0]().set_ydata(p1)
            self._3d_axes_icon[3]().set_x(pt[0])
            self._3d_axes_icon[3]().set_y(pt[1])

            p0, p1, pt = ptf(yvec)
            self._3d_axes_icon[1]().set_xdata(p0)
            self._3d_axes_icon[1]().set_ydata(p1)
            self._3d_axes_icon[4]().set_x(pt[0])
            self._3d_axes_icon[4]().set_y(pt[1])

            p0, p1, pt = ptf(zvec)
            self._3d_axes_icon[2]().set_xdata(p0)
            self._3d_axes_icon[2]().set_ydata(p1)
            self._3d_axes_icon[5]().set_x(pt[0])
            self._3d_axes_icon[5]().set_y(pt[1])

    def get_gl_uniforms(self):
        glcanvas = get_glcanvas()
        return glcanvas.get_uniforms()

    @allow_rasterization
    def draw(self, renderer):
        #        if self._use_gl and isSupportedRenderer(renderer):
        gl_len = 0
        if isSupportedRenderer(renderer):
            self._matrix_cache = self.get_proj2()
            artists = []

            artists.extend(self.images)
            artists.extend(self.collections)
            artists.extend(self.patches)
            artists.extend(self.lines)
            artists.extend(self.texts)
            artists.extend(self.artists)

            gl_obj = [a for a in artists if hasattr(a, 'is_gl')]

            gl_len = len(gl_obj)
            if gl_obj > 0:
                glcanvas = get_glcanvas()
                if (glcanvas is not None and
                        glcanvas.init):
                    glcanvas.set_lighting(**self._lighting)
                    glcanvas._gl_scale = self._gl_scale
                else:
                    return
            renderer._num_globj = gl_len
            renderer._k_globj = 0

        # axes3D seems to change frameon status....
        frameon = self.get_frame_on()
        self.set_frame_on(False)
        if self._show_3d_axes:
            self.draw_3d_axes()
            for a in self._3d_axes_icon:
                a().set_zorder(gl_len+1)
        else:
            if self._3d_axes_icon is not None:
                self.lines.remove(self._3d_axes_icon[0]())
                self.lines.remove(self._3d_axes_icon[1]())
                self.lines.remove(self._3d_axes_icon[2]())
                self.texts.remove(self._3d_axes_icon[3]())
                self.texts.remove(self._3d_axes_icon[4]())
                self.texts.remove(self._3d_axes_icon[5]())
            self._3d_axes_icon = None

        if self._gl_scale != 1.0:
            print(("gl_scale", self._gl_scale))
            xmin, xmax = self.get_xlim3d()
            ymin, ymax = self.get_ylim3d()
            zmin, zmax = self.get_zlim3d()
            dx = (xmax - xmin)/self._gl_scale/2.
            dy = (ymax - ymin)/self._gl_scale/2.
            dz = (zmax - zmin)/self._gl_scale/2.
            xmid = (xmax + xmin)/2.
            ymid = (ymax + ymin)/2.
            zmid = (zmax + zmin)/2.
            self.set_xlim3d([xmid-dx, xmid+dx])
            self.set_ylim3d([ymid-dy, ymid+dy])
            self.set_zlim3d([zmid-dz, zmid+dz])

        val = Axes3D.draw(self, renderer)

        if self._gl_scale != 1.0:
            self.set_xlim3d([xmin, xmax])
            self.set_ylim3d([ymin, ymax])
            self.set_zlim3d([zmin, zmax])

        self.set_frame_on(frameon)
        return val
